const API_URL = 'http://127.0.0.1:8000/analyze';

function createAnalyzeButton() {
  const button = document.createElement('button');
  button.innerText = 'Analyze Reviews';
  button.id = 'analyze-reviews-btn';
  button.style.cssText = `
    position: fixed;
    top: 100px;
    right: 20px;
    z-index: 9999;
    background-color: #232F3E;
    color: white;
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
  `;

  button.addEventListener('click', () => {
    button.innerText = '⏳ Analyzing...';
    button.disabled = true;
    analyzeAllReviews(button);
  });

  document.body.appendChild(button);
}

function extractReviews() {
  const reviewElements = document.querySelectorAll('[data-hook="review"]');
  const reviews = [];

  reviewElements.forEach((el) => {
    const textEl = el.querySelector('[data-hook="reviewRichContentContainer"]');
    const ratingEl = el.querySelector('[data-hook="review-star-rating"]');
    const titleEl = el.querySelector('[data-hook="reviewTitle"]');
    const helpfulEl = el.querySelector('[data-hook="helpful-vote-statement"]');

    if (textEl) {
      reviews.push({
        element: el,
        text: textEl.innerText.trim(),
        rating: ratingEl ? parseInt(ratingEl.innerText.trim()[0]) : 5,
        title: titleEl ? titleEl.innerText.trim() : "",
        helpful_vote: helpfulEl ? parseInt((helpfulEl.innerText.match(/\d+/) || [0])[0]) : 0
      });
    }
  });

  return reviews;
}

async function analyzeReview(review) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: review.text,
      rating: review.rating,
      helpful_vote: review.helpful_vote,
      title: review.title
    })
  });
  return await response.json();
}

function displayBadge(reviewElement, result) {
  const badge = document.createElement('div');
  badge.style.cssText = `
    margin-top: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
    display: inline-block;
  `;

  let bgColor = '#d4edda';
  let textColor = '#155724';
  if (result.combined_trust_score < 40) {
    bgColor = '#f8d7da';
    textColor = '#721c24';
  } else if (result.combined_trust_score < 70) {
    bgColor = '#fff3cd';
    textColor = '#856404';
  }

  badge.style.backgroundColor = bgColor;
  badge.style.color = textColor;
  badge.innerText = `Trust Score: ${result.combined_trust_score}/100 (${result.trust_label}) | Fake Risk: ${result.fake_review_risk}% | AI Risk: ${result.ai_generated_risk}%`;

  reviewElement.appendChild(badge);
}

async function analyzeAllReviews(button) {
  const reviews = extractReviews();

  if (reviews.length === 0) {
    button.innerText = 'No reviews found';
    return;
  }

  for (const review of reviews) {
    try {
      const result = await analyzeReview(review);
      displayBadge(review.element, result);
    } catch (error) {
      console.error('Error analyzing review:', error);
    }
  }

  button.innerText = `Analyzed ${reviews.length} reviews`;
}

createAnalyzeButton();