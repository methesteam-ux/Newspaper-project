"""제호 옆 날씨 귀퉁이 — Open-Meteo (API 키 불필요). 실패하면 조용히 생략한다."""
from __future__ import annotations

import logging

import requests

from models import Weather

log = logging.getLogger(__name__)

# WMO weather code → (이모지, 설명)
_WMO = [
    ({0}, "☀️", "맑음"),
    ({1}, "🌤️", "대체로 맑음"),
    ({2}, "⛅", "구름 조금"),
    ({3}, "☁️", "흐림"),
    ({45, 48}, "🌫️", "안개"),
    ({51, 53, 55, 56, 57}, "🌦️", "이슬비"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "🌧️", "비"),
    ({71, 73, 75, 77, 85, 86}, "🌨️", "눈"),
    ({95, 96, 99}, "⛈️", "뇌우"),
]


def describe(code: int) -> tuple[str, str]:
    for codes, emoji, text in _WMO:
        if code in codes:
            return emoji, text
    return "🌡️", "날씨"


def fetch_weather(city: str, lat: float, lon: float, timeout: float = 8) -> Weather | None:
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Seoul",
                "forecast_days": 1,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        emoji, text = describe(int(data["current"]["weather_code"]))
        return Weather(
            city=city,
            emoji=emoji,
            text=text,
            temp=round(float(data["current"]["temperature_2m"])),
            t_max=round(float(data["daily"]["temperature_2m_max"][0])),
            t_min=round(float(data["daily"]["temperature_2m_min"][0])),
        )
    except Exception as exc:
        log.info("날씨 정보를 가져오지 못해 생략합니다: %s", exc)
        return None
