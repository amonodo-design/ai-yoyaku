import json
import pickle
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
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


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI予約 | AIに話しかけるだけで予約が完了</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif; color: #1a1a1a; background: #fff; }

    header { background: #fff; border-bottom: 1px solid #eee; padding: 16px 24px; display: flex; align-items: center; }
    header h1 { font-size: 18px; font-weight: 700; color: #2563eb; }

    .hero { background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%); padding: 80px 24px; text-align: center; }
    .hero h2 { font-size: 36px; font-weight: 800; line-height: 1.3; margin-bottom: 16px; }
    .hero h2 span { color: #2563eb; }
    .hero p { font-size: 18px; color: #555; margin-bottom: 40px; line-height: 1.7; }
    .hero .cta { display: inline-block; background: #2563eb; color: #fff; padding: 16px 40px; border-radius: 8px; font-size: 16px; font-weight: 700; text-decoration: none; }
    .hero .cta:hover { background: #1d4ed8; }

    .how { padding: 80px 24px; max-width: 800px; margin: 0 auto; }
    .how h3 { font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 48px; }
    .steps { display: flex; flex-direction: column; gap: 32px; }
    .step { display: flex; align-items: flex-start; gap: 20px; }
    .step-num { background: #2563eb; color: #fff; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 18px; flex-shrink: 0; }
    .step-text h4 { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
    .step-text p { color: #555; line-height: 1.6; }

    .shops { background: #f8fafc; padding: 80px 24px; text-align: center; }
    .shops h3 { font-size: 28px; font-weight: 700; margin-bottom: 16px; }
    .shops p { color: #555; margin-bottom: 32px; }
    .tags { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; }
    .tag { background: #fff; border: 1px solid #ddd; padding: 8px 20px; border-radius: 999px; font-size: 15px; }

    .merit { padding: 80px 24px; max-width: 800px; margin: 0 auto; }
    .merit h3 { font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 48px; }
    .merit-list { display: flex; flex-direction: column; gap: 24px; }
    .merit-item { display: flex; gap: 16px; align-items: flex-start; }
    .merit-icon { font-size: 28px; flex-shrink: 0; }
    .merit-item h4 { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
    .merit-item p { color: #555; line-height: 1.6; }

    .contact { background: #2563eb; color: #fff; padding: 80px 24px; text-align: center; }
    .contact h3 { font-size: 28px; font-weight: 700; margin-bottom: 16px; }
    .contact p { font-size: 16px; margin-bottom: 32px; opacity: 0.9; line-height: 1.7; }
    .contact a { display: inline-block; background: #fff; color: #2563eb; padding: 16px 40px; border-radius: 8px; font-size: 16px; font-weight: 700; text-decoration: none; }
    .contact a:hover { background: #eff6ff; }

    footer { text-align: center; padding: 24px; color: #999; font-size: 13px; border-top: 1px solid #eee; }

    @media (min-width: 600px) {
      .hero h2 { font-size: 48px; }
      .steps { flex-direction: row; flex-wrap: wrap; }
      .step { flex: 1; min-width: 220px; }
    }
  </style>
</head>
<body>

<header>
  <h1>AI予約</h1>
</header>

<section class="hero">
  <h2>「近くの整体を<span>月曜14時に予約して</span>」<br>それだけで完了。</h2>
  <p>ChatGPTに話しかけるだけで予約が入る。<br>店舗側はGoogleカレンダーを使うだけ。新しいシステムは不要です。</p>
  <a href="mailto:contact@example.com" class="cta">無料で試してみる（店舗向け）</a>
</section>

<section class="how">
  <h3>どうやって使うの？</h3>
  <div class="steps">
    <div class="step">
      <div class="step-num">1</div>
      <div class="step-text">
        <h4>Googleカレンダーに「空き」を入れる</h4>
        <p>予約可能な時間帯に「空き」というタイトルで予定を追加するだけ。</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div class="step-text">
        <h4>お客さんがAIに話しかける</h4>
        <p>「渋谷の整体を月曜14時に予約して」とChatGPTに伝えるだけで自動検索・予約。</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div class="step-text">
        <h4>カレンダーが自動で更新される</h4>
        <p>「空き」が「【予約済み】田中太郎 090-XXXX」に変わって赤くなる。</p>
      </div>
    </div>
  </div>
</section>

<section class="shops">
  <h3>対応ジャンル</h3>
  <p>個人経営の小規模店舗を中心にサポートします。</p>
  <div class="tags">
    <span class="tag">整体・カイロ</span>
    <span class="tag">マッサージ</span>
    <span class="tag">美容院</span>
    <span class="tag">ネイルサロン</span>
    <span class="tag">パーソナルジム</span>
    <span class="tag">ヨガ・ピラティス</span>
    <span class="tag">エステ</span>
    <span class="tag">その他（相談可）</span>
  </div>
</section>

<section class="merit">
  <h3>店舗側のメリット</h3>
  <div class="merit-list">
    <div class="merit-item">
      <div class="merit-icon">📅</div>
      <div>
        <h4>新しいシステムを覚えなくていい</h4>
        <p>使い慣れたGoogleカレンダーがそのまま予約管理ツールになります。</p>
      </div>
    </div>
    <div class="merit-item">
      <div class="merit-icon">🤖</div>
      <div>
        <h4>AI秘書から予約が入ってくる</h4>
        <p>ChatGPTを使うお客さんが「AIに任せて予約」する時代が来ます。その入口に早めに立てます。</p>
      </div>
    </div>
    <div class="merit-item">
      <div class="merit-icon">🆓</div>
      <div>
        <h4>今なら無料でスタート</h4>
        <p>まずは試してもらう段階なので、初期費用・月額費用ともに無料です。</p>
      </div>
    </div>
  </div>
</section>

<section class="contact">
  <h3>まず話を聞いてみる</h3>
  <p>「うちの店でも使えるかな？」という相談だけでも大歓迎です。<br>30分のオンラインで説明します。</p>
  <a href="mailto:contact@example.com">無料相談する</a>
</section>

<footer>
  &copy; 2026 AI予約
</footer>

</body>
</html>
"""


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
