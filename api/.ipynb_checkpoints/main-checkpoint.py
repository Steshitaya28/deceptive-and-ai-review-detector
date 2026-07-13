# Imports and setup
from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import json
import re
import numpy as np
from scipy.sparse import hstack
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
import torch
from fastapi.middleware.cors import CORSMiddleware

# creating fastapi app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def add_private_network_header(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response
    
# Load Model 1 (Fake Review Detector)
fake_review_model = joblib.load('../saved_models/fake_review_model.pkl')
tfidf_vectorizer = joblib.load('../saved_models/tfidf_vectorizer.pkl')
numeric_scaler = joblib.load('../saved_models/numeric_scaler.pkl')

with open('../saved_models/model_metadata.json', 'r') as f:
    model1_metadata = json.load(f)

# Load Model 2 (AI Text Detector)
ai_text_model = joblib.load('../saved_models/ai_text_model.pkl')
ai_tfidf_vectorizer = joblib.load('../saved_models/ai_tfidf_vectorizer.pkl')
ai_numeric_scaler = joblib.load('../saved_models/ai_numeric_scaler.pkl')

with open('../saved_models/ai_model_metadata.json', 'r') as f:
    model2_metadata = json.load(f)

# Loading GPT2 for perplexity calculation
gpt2_tokenizer = GPT2TokenizerFast.from_pretrained('gpt2')
gpt2_model = GPT2LMHeadModel.from_pretrained('gpt2')
gpt2_model.eval()

print("All models loaded successfully.")

# Required Functions
def calculate_perplexity(text, tokenizer, model, max_length=512):
    encodings = tokenizer(text, return_tensors='pt', truncation=True, max_length=max_length)
    input_ids = encodings.input_ids
    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        loss = outputs.loss
    perplexity = torch.exp(loss).item()
    return perplexity
PERPLEXITY_CAP = 747.325339

def calculate_burstiness(text):
    sentences = text.split('.')
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) < 2:
        return 0
    lengths = [len(s.split()) for s in sentences]
    return np.std(lengths)

def calculate_vocab_diversity(text):
    words = text.lower().split()
    if len(words) == 0:
        return 0
    return len(set(words)) / len(words)

class ReviewInput(BaseModel):
    text: str
    rating: int
    helpful_vote: int = 0
    title: str = ""

def clean_text(text):
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@app.post("/analyze")
def analyze_review(review: ReviewInput):
    cleaned_text = clean_text(review.text)
    
    # Model 1 features
    word_count = len(cleaned_text.split())
    title_length = len(review.title)
    is_extreme_rating = 1 if review.rating in [1, 5] else 0
    
    model1_numeric = np.array([[review.rating, review.helpful_vote, word_count, 
                                  is_extreme_rating, title_length]])
    model1_numeric_scaled = numeric_scaler.transform(model1_numeric)
    
    model1_tfidf = tfidf_vectorizer.transform([cleaned_text])
    model1_features = hstack([model1_tfidf, model1_numeric_scaled])
    
    fake_probability = fake_review_model.predict_proba(model1_features)[0][1]

    # Model 2 features
    raw_perplexity = calculate_perplexity(review.text, gpt2_tokenizer, gpt2_model)
    perplexity_capped = min(raw_perplexity, PERPLEXITY_CAP)
    burstiness = calculate_burstiness(review.text)
    vocab_diversity = calculate_vocab_diversity(review.text)
    
    model2_numeric = np.array([[perplexity_capped, burstiness, vocab_diversity]])
    model2_numeric_scaled = ai_numeric_scaler.transform(model2_numeric)
    
    model2_tfidf = ai_tfidf_vectorizer.transform([review.text])
    model2_features = hstack([model2_tfidf, model2_numeric_scaled])
    
    ai_probability = ai_text_model.predict_proba(model2_features)[0][1]

    # Combine into trust score
    fake_weight = 0.6
    ai_weight = 0.4
    
    risk_score = (fake_probability * fake_weight) + (ai_probability * ai_weight)
    trust_score = round((1 - risk_score) * 100)
    
    if trust_score >= 70:
        trust_label = "High Trust"
    elif trust_score >= 40:
        trust_label = "Moderate - Some Concerns"
    else:
        trust_label = "Low Trust - Proceed Carefully"
    
    return {
        "fake_review_risk": round(fake_probability * 100, 1),
        "ai_generated_risk": round(ai_probability * 100, 1),
        "combined_trust_score": trust_score,
        "trust_label": trust_label
    }
    