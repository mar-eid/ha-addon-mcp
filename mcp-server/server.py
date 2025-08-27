import os
from datetime import datetime
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="MCP Server (HA)", version="0.1.0")

# Konfig
READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
PORT = int(os.getenv("MCP_PORT", "8099"))

# TODO: sett opp faktisk DB-klient (psycopg2 / asyncpg)
def fake_series(start: str, end: str, points: int = 24):
    from datetime import timedelta
    s = datetime.fromisoformat(start.replace("Z",""))
    e = datetime.fromisoformat(end.replace("Z",""))
    dt = (e - s) / points
    out = []
    val = 20.0
    for i in range(points):
        out.append({"t": (s + dt*i).isoformat() + "Z", "v": round(val, 2)})
        val += 0.1
    return out

class HistoryRequest(BaseModel):
    entity_id: str
    start: str
    end: str
    interval: Optional[str] = "1h"
    agg: Optional[Literal["raw","last","mean","min","max","sum"]] = "last"

class StatsRequest(BaseModel):
    statistic_id: str
    start: str
    end: str
    period: Literal["hour","day"] = "hour"
    fields: Optional[List[Literal["mean","min","max","sum"]]] = ["mean"]

class StatsBulkRequest(BaseModel):
    statistic_ids: List[str]
    start: str
    end: str
    period: Literal["hour","day"] = "day"
    fields: Optional[List[Literal["mean","min","max","sum"]]] = ["mean","max","min"]
    page_size: int = 2000
    page: int = 0

@app.get("/health")
def health():
    return {"ok": True, "read_only": READ_ONLY, "ts": datetime.utcnow().isoformat() + "Z"}

@app.post("/tools/ha.get_history")
def ha_get_history(req: HistoryRequest):
    # TODO: bruk Recorder/Timescale. Nå: mock.
    return {"series": fake_series(req.start, req.end, 48)}

@app.post("/tools/ha.get_statistics")
def ha_get_statistics(req: StatsRequest):
    # TODO: bruk statistics/statistics_meta
    items = fake_series(req.start, req.end, 48)
    for item in items:
        item["mean"] = item.pop("v")
    return {"series": items}

@app.post("/tools/ha.get_statistics_bulk")
def ha_get_statistics_bulk(req: StatsBulkRequest):
    # TODO: ekte bulk fra DB
    out = {}
    for sid in req.statistic_ids:
        items = fake_series(req.start, req.end, 30)
        for item in items:
            m = item.pop("v")
            item.update({"mean": m, "min": m-0.5, "max": m+0.5})
        out[sid] = items
    return {"items": out, "next_page": None}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

