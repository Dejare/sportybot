"""Inspect the actual data structure from the working endpoints."""
import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.sportybet.com",
    "Referer": "https://www.sportybet.com/ng/",
    "x-requested-with": "XMLHttpRequest",
}

BASE = "https://www.sportybet.com/api/ng"

# 1) Live/Prematch events with SR sport ID
print("=" * 60)
print("LIVE OR PREMATCH EVENTS (working)")
print("=" * 60)
r = requests.get(
    f"{BASE}/factsCenter/liveOrPrematchEvents",
    params={"sportId": "sr:sport:1", "pageSize": 3, "pageNum": 1},
    headers=HEADERS,
    timeout=15
)
data = r.json()
print(f"Status: {r.status_code}")
print(f"bizCode: {data.get('bizCode')}")
print(f"message: {data.get('message')}")
events = data.get("data", [])
print(f"Event count: {len(events)}")

if events:
    # Print first event structure
    ev = events[0]
    print(f"\nFirst event keys: {list(ev.keys())}")
    print(json.dumps(ev, indent=2, default=str)[:2000])

# 2) Test with group=LiveNow for live-only
print("\n" + "=" * 60)
print("LIVE ONLY (group=LiveNow)")
print("=" * 60)
r2 = requests.get(
    f"{BASE}/factsCenter/liveOrPrematchEvents",
    params={"sportId": "sr:sport:1", "pageSize": 3, "Num": 1, "group": "LiveNow"},
    headers=HEADERS,
    timeout=15
)
data2 = r2.json()
print(f"Status: {r2.status_code}, bizCode: {data2.get('bizCode')}, events: {len(data2.get('data', []))}")

# 3) Booking with a valid code
print("\n" + "=" * 60)
print("BOOKING CODE")
print("=" * 60)
r3 = requests.get(
    f"{BASE}/orders/share/booking-code",
    params={"bookingCode": "J9NU3F"},
    headers=HEADERS,
    timeout=10
)
data3 = r3.json()
print(f"Status: {r3.status_code}, bizCode: {data3.get('bizCode')}, message: {data3.get('message')}")
if data3.get("data"):
    print(f"Data keys: {list(data3['data'].keys())}")
    print(json.dumps(data3["data"], indent=2, default=str)[:1000])

# Save full output
with open("test_data.json", "w") as f:
    json.dump({
        "events_sample": events[:1] if events else [],
        "booking_response": data3,
    }, f, indent=2, default=str)
