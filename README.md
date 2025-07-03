# Hospital Inventory Management System

This project manages hospital asset inventories across multiple facilities using a Tornado-based backend and PostgreSQL database.

## Project Structure

```
hospital_inventory/
├── backend/
│   ├── database/
│   │   └── asset_db.sql
│   ├── scripts/
│   │   ├── bulk_load_assets.py
│   │   └── hashpwd.py
│   ├── api.py
│   ├── core.py
│   └── tornado_app.py
├── data/
│   ├── assets_HQ.xlsx
│   ├── assets_MPEAST.xlsx
│   ├── assets_NDH.xlsx
│   └── assets_SHARON.xlsx
├── README.md
├── requirements.txt
```

## Setup Instructions

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up the PostgreSQL database using:
```bash
psql -U <username> -d <database_name> -f backend/database/asset_db.sql
```

3. Start the Tornado app:
```bash
python backend/tornado_app.py
```
