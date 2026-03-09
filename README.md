# DigitalBazar - Digital Products Marketplace

A production-grade marketplace platform for digital products including software licenses, templates, themes, graphics, music, fonts, courses, and ebooks. Built with Django REST Framework and Next.js.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [User Roles](#user-roles)
- [Business Logic](#business-logic)
- [Roadmap](#roadmap)

---

## Overview

DigitalBazar connects digital content creators with buyers through a secure, scalable marketplace. Sellers upload digital products, set pricing and licensing terms, and receive payouts. Buyers browse, purchase, and instantly download products. The platform handles payments via Stripe, manages license keys, enforces download limits, and provides comprehensive analytics.

---

## Features

### Core Marketplace
- Multi-category product listings (software, templates, themes, graphics, music, fonts, courses, ebooks)
- Advanced search with filters (category, price range, rating, license type, file format)
- Product previews (image galleries, audio samples, live demos)
- Instant secure downloads with signed URLs and expiration
- Version management for product updates

### License Management
- Multiple license tiers per product (Personal, Commercial, Extended)
- Automatic license key generation (UUID-based and custom patterns)
- License validation API for third-party integration
- Download limits per license tier
- License transfer and revocation capabilities

### Payments and Payouts
- Stripe integration for checkout (cards, wallets)
- Split payments between platform and seller
- Configurable platform commission rates
- Automated seller payout scheduling
- Refund request workflow with approval process
- Tax calculation support

### Seller Dashboard
- Real-time sales analytics with charts
- Revenue tracking (daily, weekly, monthly, yearly)
- Product performance metrics (views, conversions, downloads)
- Earnings and payout history
- Customer demographics overview

### Affiliate System
- Seller-configurable affiliate programs
- Unique referral link generation
- Commission tracking and automated payouts
- Affiliate performance dashboard
- Cookie-based attribution with configurable duration

### Reviews and Ratings
- Verified purchase reviews only
- Star ratings with written feedback
- Seller response capability
- Review moderation by admins
- Aggregate rating calculations

### Security
- JWT authentication with refresh tokens
- Role-based access control (Admin, Seller, Buyer, Affiliate)
- File upload validation and malware scanning hooks
- Rate limiting on API endpoints
- CORS and CSRF protection
- Secure file storage with signed download URLs

---

## Architecture

```
                    +------------------+
                    |   Nginx Reverse  |
                    |      Proxy       |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------v---------+       +-----------v-----------+
    |   Next.js (SSR)   |       |   Django REST API     |
    |   Frontend :3000  |       |   Backend :8000       |
    +-------------------+       +-----------+-----------+
                                            |
                        +-------------------+-------------------+
                        |                   |                   |
              +---------v------+  +---------v------+  +---------v------+
              |  PostgreSQL    |  |     Redis       |  |  Celery Worker |
              |  Database      |  |  Cache/Broker   |  |  Async Tasks   |
              +----------------+  +----------------+  +----------------+
                                                              |
                                                    +---------v------+
                                                    |  Stripe API    |
                                                    |  (Payments)    |
                                                    +----------------+
```

### Data Flow
1. Users interact with the Next.js frontend
2. Frontend communicates with Django REST API via HTTP/JSON
3. API handles authentication, business logic, and data persistence
4. Celery workers process background tasks (email notifications, report generation, payout processing)
5. Redis serves as both cache layer and Celery message broker
6. Stripe handles all payment processing
7. Nginx routes traffic and serves static/media files

---

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Frontend       | Next.js 14, React 18, Tailwind CSS |
| Backend        | Django 5.0, Django REST Framework  |
| Database       | PostgreSQL 16                      |
| Cache/Broker   | Redis 7                            |
| Task Queue     | Celery 5                           |
| Payments       | Stripe API                         |
| Containerization | Docker, Docker Compose           |
| Reverse Proxy  | Nginx                              |
| Authentication | JWT (SimpleJWT)                    |
| File Storage   | Local / S3-compatible              |

---

## Project Structure

```
digitalbazar/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── celery.py
│   ├── apps/
│   │   ├── __init__.py
│   │   ├── accounts/        # User management, profiles
│   │   ├── products/        # Product catalog, categories, licenses
│   │   ├── orders/          # Orders, downloads, license keys
│   │   ├── payments/        # Stripe integration, payouts, refunds
│   │   ├── affiliates/      # Affiliate programs, commissions
│   │   ├── analytics/       # Views, downloads, sales reports
│   │   └── reviews/         # Product reviews and ratings
│   └── utils/
│       ├── __init__.py
│       ├── pagination.py
│       ├── file_handler.py
│       ├── license_generator.py
│       └── exceptions.py
└── frontend/
    ├── package.json
    ├── next.config.js
    └── src/
        ├── app/
        │   ├── layout.jsx
        │   ├── page.jsx
        │   ├── products/
        │   ├── seller/
        │   ├── dashboard/
        │   ├── cart/
        │   └── auth/
        ├── components/
        │   ├── layout/
        │   ├── products/
        │   ├── dashboard/
        │   └── auth/
        ├── lib/
        │   ├── api.js
        │   └── auth.js
        ├── context/
        │   ├── AuthContext.jsx
        │   └── CartContext.jsx
        └── styles/
            └── globals.css
```

---

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/your-org/digitalbazar.git
cd digitalbazar

# Copy environment variables
cp .env.example .env

# Update .env with your Stripe keys and other secrets

# Build and start all services
docker-compose up --build

# Run database migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Load sample data (optional)
docker-compose exec backend python manage.py loaddata initial_categories
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1/
- Admin Panel: http://localhost:8000/admin/

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py migrate
python manage.py runserver
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Environment Variables

See `.env.example` for all required variables. Key settings:

| Variable              | Description                          |
|-----------------------|--------------------------------------|
| `SECRET_KEY`          | Django secret key                    |
| `DATABASE_URL`        | PostgreSQL connection string         |
| `REDIS_URL`           | Redis connection string              |
| `STRIPE_SECRET_KEY`   | Stripe API secret key                |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key            |
| `STRIPE_WEBHOOK_SECRET`  | Stripe webhook signing secret     |
| `PLATFORM_COMMISSION` | Platform fee percentage (0-100)      |
| `AWS_STORAGE_BUCKET`  | S3 bucket for file storage (optional)|

---

## API Documentation

### Authentication

| Method | Endpoint                      | Description           |
|--------|-------------------------------|-----------------------|
| POST   | `/api/v1/auth/register/`      | Register new user     |
| POST   | `/api/v1/auth/login/`         | Obtain JWT tokens     |
| POST   | `/api/v1/auth/token/refresh/` | Refresh access token  |
| GET    | `/api/v1/auth/me/`            | Get current user      |
| PUT    | `/api/v1/auth/me/`            | Update current user   |

### Products

| Method | Endpoint                           | Description              |
|--------|------------------------------------|--------------------------|
| GET    | `/api/v1/products/`                | List products (filtered) |
| POST   | `/api/v1/products/`                | Create product (seller)  |
| GET    | `/api/v1/products/{slug}/`         | Product detail           |
| PUT    | `/api/v1/products/{slug}/`         | Update product (owner)   |
| DELETE | `/api/v1/products/{slug}/`         | Delete product (owner)   |
| GET    | `/api/v1/products/categories/`     | List categories          |
| GET    | `/api/v1/products/{slug}/reviews/` | Product reviews          |

### Orders

| Method | Endpoint                          | Description              |
|--------|-----------------------------------|--------------------------|
| POST   | `/api/v1/orders/checkout/`        | Create order + payment   |
| GET    | `/api/v1/orders/`                 | List user orders         |
| GET    | `/api/v1/orders/{id}/`            | Order detail             |
| GET    | `/api/v1/orders/{id}/download/{file_id}/` | Download file    |
| GET    | `/api/v1/orders/licenses/`        | List user licenses       |

### Payments

| Method | Endpoint                              | Description               |
|--------|---------------------------------------|---------------------------|
| POST   | `/api/v1/payments/create-intent/`     | Create Stripe PaymentIntent |
| POST   | `/api/v1/payments/webhook/`           | Stripe webhook handler     |
| GET    | `/api/v1/payments/payouts/`           | Seller payout history      |
| POST   | `/api/v1/payments/refund-request/`    | Request refund             |

### Analytics (Seller)

| Method | Endpoint                            | Description              |
|--------|-------------------------------------|--------------------------|
| GET    | `/api/v1/analytics/dashboard/`      | Dashboard summary        |
| GET    | `/api/v1/analytics/sales/`          | Sales data               |
| GET    | `/api/v1/analytics/products/`       | Product performance      |
| GET    | `/api/v1/analytics/downloads/`      | Download statistics      |

### Affiliates

| Method | Endpoint                               | Description              |
|--------|----------------------------------------|--------------------------|
| GET    | `/api/v1/affiliates/programs/`         | List affiliate programs  |
| POST   | `/api/v1/affiliates/links/`            | Generate affiliate link  |
| GET    | `/api/v1/affiliates/commissions/`      | Commission history       |
| GET    | `/api/v1/affiliates/stats/`            | Affiliate statistics     |

### Reviews

| Method | Endpoint                      | Description              |
|--------|-------------------------------|--------------------------|
| POST   | `/api/v1/reviews/`            | Create review            |
| PUT    | `/api/v1/reviews/{id}/`       | Update review            |
| DELETE | `/api/v1/reviews/{id}/`       | Delete review            |
| POST   | `/api/v1/reviews/{id}/reply/` | Seller reply             |

---

## User Roles

### Admin
- Full platform management
- User and seller verification
- Content moderation
- Commission rate configuration
- Refund approval
- Platform analytics access

### Seller
- Product creation and management
- Pricing and license configuration
- Sales analytics dashboard
- Payout management
- Affiliate program setup
- Customer review responses

### Buyer
- Product browsing and purchasing
- Download management
- License key access
- Order history
- Review submission
- Affiliate participation

### Affiliate
- Browse affiliate programs
- Generate referral links
- Track referral conversions
- Commission earnings and payouts

---

## Business Logic

### Commission Structure
- Platform takes a configurable commission (default 15%) on each sale
- Seller receives (100% - commission) of each sale
- Affiliate commissions are paid from the seller's portion
- Minimum payout threshold: $50.00

### Licensing Model
- **Personal License**: Single user, non-commercial use. One download allowed.
- **Commercial License**: Business use, one project. Up to 5 downloads.
- **Extended License**: Unlimited projects, redistribution rights. Unlimited downloads.
- License keys are auto-generated and validated via API.

### Refund Policy
- Refund requests within 30 days of purchase
- Requires written reason
- Admin approval required
- Automatic Stripe refund on approval
- License keys revoked on refund

### Download Security
- Signed URLs with 24-hour expiration
- Download count tracking and limits per license
- IP logging for fraud detection
- File integrity verification via checksums

### Affiliate Attribution
- 30-day cookie-based attribution window
- Last-click attribution model
- Minimum commission: $1.00 per sale
- Commission rates set per product by seller (default 10%)

---

## Roadmap

### Phase 1 - MVP (Current)
- [x] User authentication and profiles
- [x] Product CRUD with file uploads
- [x] Category and tag system
- [x] Stripe payment integration
- [x] Secure file downloads
- [x] License key generation
- [x] Basic seller dashboard
- [x] Review system

### Phase 2 - Growth
- [ ] Subscription-based products (recurring billing)
- [ ] Product bundles and collections
- [ ] Discount codes and promotional pricing
- [ ] Email notification system (transactional emails)
- [ ] Wishlist functionality
- [ ] Advanced search with Elasticsearch
- [ ] Multi-currency support

### Phase 3 - Scale
- [ ] S3/CloudFront file delivery
- [ ] CDN integration for global distribution
- [ ] Webhook system for third-party integrations
- [ ] Public API with OAuth2 for developers
- [ ] Mobile app (React Native)
- [ ] AI-powered product recommendations
- [ ] Advanced fraud detection

### Phase 4 - Enterprise
- [ ] White-label marketplace solution
- [ ] Custom domain support for sellers
- [ ] Team accounts and role management
- [ ] SLA and enterprise support tiers
- [ ] Advanced reporting and data exports
- [ ] Marketplace API for headless commerce
