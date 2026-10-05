# Notification Management

## Delivery and access

Notifications are materialized per active recipient, so each user has independent read state. The notification API derives both `company_id` and `user_id` from the authenticated principal; request parameters cannot select another tenant or another user's inbox. Mark-read operations filter by notification ID, company, and authenticated user. There is no delete/clear endpoint.

## Role matrix

| Event | Company Admin / Super Admin | Analyst | Viewer |
| --- | --- | --- | --- |
| Stockout / critical inventory | Yes | No | No |
| Low stock | Yes | Yes | No |
| Forecast stockout risk | Yes | Yes | No |
| Overstock forecast | Yes | Yes | No |
| Import complete, partial, or failed | Yes | No | No |
| High-value sale | Yes | Yes | No |
| System alert | Yes | No | No |

Viewer notifications are not currently generated; this follows least privilege until a viewer-safe event is explicitly defined.

## Priority and conditions

- Critical: available stock is zero.
- High: forecasted demand reaches or exceeds positive available stock during the forecast window; also used for failed imports.
- Medium: available stock is below the inventory reorder point, or a sale is at least 10,000 in the application's monetary units.
- Low: forecast indicates overstock, or a successful import completes without row errors.
- An inventory record has a configurable reorder point but no maximum-stock field. As a fallback, stock greater than four times the reorder point is treated as overstock. Once a forecast recommendation is available, its overstock-risk result is used.

## Duplicate prevention and lifecycle

Condition-based alerts use a stable event key per company resource and condition. An active matching alert is not re-created on repeated evaluation. When its condition clears, `resolved_at` is set and the old alert expires after seven days. If the condition reoccurs, the existing row is reopened as unread with refreshed details instead of adding a duplicate. Event notifications such as imports and high-value sales use an event key based on the import or sale ID. Unresolved event notices do not expire automatically.

## Real-time and filtering

The React Query notification bell polls unread count every 20 seconds and polls the list while its center is open. This is a lightweight fit for the existing REST/query architecture and avoids introducing WebSocket infrastructure. The API supports pagination and combined read-state, type, and priority filters.

## API

- `GET /api/notifications?page=1&page_size=20&read=unread&type=low-stock&priority=medium`
- `GET /api/notifications/unread-count`
- `PATCH /api/notifications/{id}/read`
- `PATCH /api/notifications/read-all`
