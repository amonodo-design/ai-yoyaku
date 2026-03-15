import json
import pickle
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = FastAPI(title="AI予約API", description="美容院・整体・ジムなどの予約をAI秘書から行うためのAPI", version="1.0.0")

SHOPS_FILE = Path(__file__).parent / "shops.json"
TOKEN_FILE = Path(__file__).parent / "token.pickle"

JST = timezone(timedelta(hours=9))
COLOR_RESERVED = "11"  # Tomato (赤)


def load_shops():
    with open(SHOPS_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_calendar_service():
    token_b64 = os.environ.get("GOOGLE_TOKEN_BASE64")
    if token_b64:
        token_data = json.loads(base64.b64decode(token_b64).decode())
        creds = Credentials(
            token=token_data["token"],
            refresh_token=token_data["refresh_token"],
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=token_data["scopes"],
        )
    else:
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    return build("calendar", "v3", credentials=creds)


def get_day_range(date: str):
    day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=JST)
    day_end = day_start + timedelta(days=1)
    return day_start.isoformat(), day_end.isoformat()


def fetch_available_events(service, calendar_id: str, date: str):
    time_min, time_max = get_day_range(date)
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return [e for e in events.get("items", []) if e.get("summary") == "空き"]


@app.get("/availability")
def get_availability(
    date: str = Query(..., description="日付（例：2026-03-23）"),
    genre: str = Query(None, description="ジャンル（例：整体、ヨガ、ジム）"),
    area: str = Query(None, description="エリア（例：渋谷、新宿）"),
):
    shops = load_shops()
    service = get_calendar_service()
    results = []
    for shop in shops:
        if genre and shop["genre"] != genre:
            continue
        if area and shop["area"] != area:
            continue
        events = fetch_available_events(service, shop["calendar_id"], date)
        slots = []
        for event in events:
            start = event["start"].get("dateTime", "")
            if start:
                dt = datetime.fromisoformat(start).astimezone(JST)
                slots.append(dt.strftime("%H:%M"))
        if slots:
            results.append({
                "shop_name": shop["name"],
                "available_times": slots,
                "address": shop["address"],
            })
    return results


class ReservationRequest(BaseModel):
    shop_name: str
    datetime: str
    customer_name: str
    customer_phone: str


@app.post("/reservation")
def create_reservation(req: ReservationRequest):
    shops = load_shops()

    shop = next((s for s in shops if s["name"] == req.shop_name), None)
    if shop is None:
        raise HTTPException(status_code=404, detail=f"店舗「{req.shop_name}」が見つかりません")

    parts = req.datetime.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="datetime は「YYYY-MM-DD HH:MM」の形式で指定してください")
    date, time = parts

    try:
        service = get_calendar_service()
        events = fetch_available_events(service, shop["calendar_id"], date)

        target_event = None
        for event in events:
            start = event["start"].get("dateTime", "")
            if start:
                dt = datetime.fromisoformat(start).astimezone(JST)
                if dt.strftime("%H:%M") == time:
                    target_event = event
                    break

        if target_event is None:
            raise HTTPException(
                status_code=404,
                detail=f"{req.shop_name} の {req.datetime} は空き枠がありません",
            )

        target_event["summary"] = f"【予約済み】{req.customer_name} {req.customer_phone}"
        target_event["colorId"] = COLOR_RESERVED

        service.events().update(
            calendarId=shop["calendar_id"],
            eventId=target_event["id"],
            body=target_event,
        ).execute()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カレンダー更新に失敗しました: {str(e)}")

    return {
        "status": "confirmed",
        "message": f"{req.shop_name}の{req.datetime}で予約が完了しました。担当者から確認の連絡が来ることがあります。",
    }
