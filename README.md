# Inventory Management System

**Enterprise Inventory** is the Django and React version of this project. It adds a buyer stockroom, supplier-specific quotation workflows, and a background worker for in-app notifications.

| Capability | What you can do |
| --- | --- |
| Stockroom | Create SKUs, record receipts and shipments, and review the movement history. |
| Purchasing | Request a supplier quote, review the submitted price, and accept an offer. |
| Supplier workspace | View assigned requests, submit unit prices, and follow accepted quotes. |
| Notifications | Receive updates on requests, quoted prices, and acceptances. |

[Run Enterprise Inventory locally](enterprise/README.md)

The original Django application remains at the repository root. The new app lives in `enterprise/` and creates its own SQLite database.
