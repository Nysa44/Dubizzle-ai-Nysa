
# Demo / Terminal Evidence

Use this transcript as the exact flow to reproduce for assessment evidence.

## 1. Backend health

```text
GET /health

{
  "status": "ok",
  "project": "Dubizzle Nysa",
  "inventory_rows": 100
}
```

## 2. Multi-turn inventory conversation

```text
User: Show me Bentleys

Nysa: I found 7 matching listings. The strongest matches include ...
[Match Radar displays the verified Bentley cards]

User: What's the mileage on the second one?

Nysa: [returns the second active result and its mileage when the Excel
listing states one; otherwise says "Mileage not stated".]
```

## 3. Cross-session memory

```text
User: I like the second one

Nysa: Saved [vehicle] to your favourites.

User: [clicks New conversation]

User: What have I saved?

Nysa: [returns the saved listing from SQLite]
```

## 4. Viewing workflow

```text
User: I want to book the second one Saturday at 3 PM

Nysa: Please confirm: [vehicle] on [Saturday date at 3:00 PM].
Reply "confirm" to book it.

User: confirm

Nysa: You're booked. [vehicle] is confirmed. Your reference is #BK-XXXXXXXX.
```

## 5. Guardrail

```text
User: Write me Python code

Nysa: I can help with car shopping on dubizzle — searching the provided
inventory, comparing listings, remembering preferences, qualifying
enquiries, and booking viewing slots. I can't help with unrelated requests.
```
