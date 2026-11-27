# Enterprise Inventory

A B2B purchasing and stock-management app built with Django and React. Buyers manage the product catalog, record stock movements, request supplier quotes, and accept offers. Suppliers see the requests assigned to them and submit unit prices. A separate worker delivers in-app notifications for quotation activity.

## Run locally

Requires Python 3.10+ and Node.js 20.19+ or 22.12+. From this directory in PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
$env:INVENTORY_DEBUG = "1"
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_demo
.venv/Scripts/python.exe manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). In a second terminal from this directory, run the notification worker:

```powershell
$env:INVENTORY_DEBUG = "1"
.venv/Scripts/python.exe manage.py process_notifications --watch
```

On macOS or Linux, use `.venv/bin/python` and replace the PowerShell environment command with `export INVENTORY_DEBUG=1`.

| Demo username | Role | Password |
| --- | --- | --- |
| `buyer` | Buyer | `inventory-demo` |
| `supplier` | Northline Supply | `inventory-demo` |
| `supplier2` | Meridian Industrial | `inventory-demo` |

Try the full flow by requesting a quote from Northline Supply as the buyer, submitting a price as `supplier`, and accepting it as the buyer. Use separate browser sessions to watch notifications arrive as the worker processes the queue. Record a separate positive stock movement once the goods arrive.

## How it works

- Django serves the frontend and JSON API on the same origin. It enforces session authentication, CSRF protection, and authorization on the server.
- Buyer accounts use Django's staff flag. Each supplier is linked to a non-staff user and has access only to its own quotations. A superuser can create users and associate suppliers through `/admin/`.
- Stock adjustments update the quantity and write a movement record in one transaction. Updates that would make stock negative are rejected.
- Quotation changes and notification jobs commit together. The worker delivers each queued job as one in-app notification. Run it without `--watch` to drain the queue once and exit.
- Local development uses a new SQLite database. Existing data from the original project lives in a separate database and has no automatic import.

Run the workflow tests with `.venv/Scripts/python.exe manage.py test` after setting `INVENTORY_DEBUG=1`.
