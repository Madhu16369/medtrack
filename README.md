# 🏥 MedTrack — Smart Hospital Inventory & Expiry Predictor

MedTrack is a web-based hospital inventory management system built to reduce
the wastage of medical supplies caused by unnoticed expiry dates. It gives
hospital staff a single platform to track medicines, surgical kits, and
implants — from stock intake to expiry monitoring to reorder planning.

## 📌 Problem It Solves

Hospitals often rely on manual inventory tracking, which leads to expired
stock going unnoticed, human error in record-keeping, time-consuming audits,
and critical items running out during emergencies. MedTrack automates these
processes with barcode/QR scanning, predictive expiry alerts, and a live
monitoring dashboard.

## ✨ Features

- **Role-Based Authentication** — Secure login/registration with separate
  access levels for Inventory Managers and Nurses, with encrypted passwords.
- **Inventory Management (CRUD)** — Add, edit, delete, and search medical
  supplies with full batch, expiry, supplier, and department details.
- **QR Code Generation** — Every inventory item automatically receives a
  unique, scannable QR code.
- **Barcode/QR Code Scanning** — Webcam-based scanning to instantly look up
  an item and issue or receive stock.
- **Expiry Prediction & Alerts** — Automatic 30/60/90-day expiry windows
  with color-coded status (Green/Yellow/Red) and a live alert badge.
- **Stock Monitoring Dashboard** — Real-time cards, charts, and
  department-wise stock visibility.
- **Purchase Order Recommendations** — Automatic reorder quantity
  suggestions for items below their minimum stock threshold.
- **Reports** — Downloadable CSV reports for expired items, low-stock items,
  and full inventory.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Backend Framework | Flask |
| Database | SQLite |
| ORM | SQLAlchemy (Flask-SQLAlchemy) |
| Authentication | Flask-Login + bcrypt |
| QR Code Generation | qrcode + Pillow |
| QR/Barcode Scanning | html5-qrcode (JavaScript) |
| Frontend | HTML, Bootstrap 5, Chart.js |
| Reports | pandas (CSV export) |
| Version Control | Git + GitHub |

## 📂 Project Structure
medtrack/
├── app.py # Main Flask application and routes
├── models.py # Database models and expiry-status logic
├── extensions.py # Flask extension instances (db, login manager)
├── requirements.txt # Python dependencies
├── static/
│ ├── css/ # Custom stylesheet
│ ├── js/ # JavaScript assets
│ └── qrcodes/ # Auto-generated QR code images
└── templates/ # HTML templates (Jinja2)


## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- Git

### Installation

1. Clone the repository:
```bash
   git clone https://github.com/YOUR-USERNAME/medtrack.git
   cd medtrack
```

2. Create and activate a virtual environment:
```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
```

3. Install dependencies:
```bash
   pip install -r requirements.txt
```

4. Run the application:
```bash
   python app.py
```

5. Open your browser and go to:
   http://127.0.0.1:5000

## 🧩 Core Modules

1. User Authentication
2. Inventory Management
3. Barcode / QR Code Scanner
4. Expiry Prediction & Alerts
5. Stock Monitoring Dashboard
6. Purchase Order Recommendation
7. Reports

## 📄 License

This project was developed for academic purposes as part of a final-year
Computer Science and Engineering project.
