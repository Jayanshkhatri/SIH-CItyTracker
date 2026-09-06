"""Deterministic Phase 8 analytics for Steps 2.38 through 2.43.

This local, machine-readable layer consumes the Phase 7 retrieval structure and
the Step 2.37 network adapter.  It does not alter identities, associations, or
the database; all inclusion/exclusion and distance provenance are explicit.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import importlib.util
from pathlib import Path
from statistics import median
import sys
from typing import Any, Iterable

import trajectory as engine
from trajectory_phase7 import Phase7TrajectoryRepository, step_231

_network_spec = importlib.util.spec_from_file_location("trajectory_step_2_37", Path(__file__).with_name("trajectory_step_2.37.py"))
if _network_spec is None or _network_spec.loader is None:
    raise RuntimeError("Unable to load verified Step 2.37")
_network_module = importlib.util.module_from_spec(_network_spec)
sys.modules[_network_spec.name] = _network_module
_network_spec.loader.exec_module(_network_module)
ProductionCameraNetwork = _network_module.ProductionCameraNetwork
verify_step_2_37 = _network_module.verify_step_2_37

MAX_SPEED_KMH = engine.MAX_PLAUSIBLE_SPEED_KMH
MAX_GAP_SECONDS = engine.MAX_TRAJECTORY_GAP_SECONDS
CONGESTION_THRESHOLDS = {"light_volume": 2, "moderate_volume": 5, "heavy_volume": 10,
                         "slow_speed_kmh": 20, "very_slow_speed_kmh": 10,
                         "delay_ratio": 1.5, "severe_delay_ratio": 2.0}


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%H:%M:%S")


def _seconds(first: str, second: str) -> float:
    return (_time(second) - _time(first)).total_seconds()


class Phase8Analytics:
    """Explainable anomaly, movement, flow, time, congestion and OD analytics."""

    def __init__(self, network: ProductionCameraNetwork) -> None:
        self.network = network

    def anomalies(self, trajectories: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for item in trajectories:
            identity, tid = item["identity"], item["trajectory_id"]
            events = self._events(item)
            if identity["quality_score"] < engine.REVIEW_REQUIRED_SCORE:
                alerts.append(self._alert(tid, "LOW_TRAJECTORY_QUALITY", "LOW", None, None,
                    {"quality_score": identity["quality_score"]}, "Quality is below analytics review threshold."))
            if any(a["status"] == "REVIEW" for a in item["associations"]):
                alerts.append(self._alert(tid, "IDENTITY_AMBIGUITY", "LOW", None, None,
                    {"review_associations": True}, "Association evidence remains under review."))
            abnormal = []
            for previous, current in zip(events, events[1:]):
                route = self.network.route(previous["camera_id"], current["camera_id"])
                observed = _seconds(previous["timestamp"], current["timestamp"])
                evidence = {"route": route, "observed_travel_seconds": observed,
                            "event_ids": [previous["id"], current["id"]]}
                if route["status"] != "CONNECTED":
                    abnormal.append(self._alert(tid, "IMPOSSIBLE_ROUTE", "CRITICAL", previous, current, evidence,
                        "No connected directed road-network path exists."))
                    continue
                if observed <= 0:
                    abnormal.append(self._alert(tid, "INVALID_TRANSITION_TIME", "HIGH", previous, current, evidence,
                        "Transition time is zero or negative."))
                    continue
                speed = route["distance_km"] / observed * 3600
                evidence["observed_speed_kmh"] = speed
                limits = [limit for limit in route["speed_limit_kmh"] if limit]
                if speed > MAX_SPEED_KMH:
                    abnormal.append(self._alert(tid, "UNREALISTIC_SPEED", "HIGH", previous, current, evidence,
                        f"Observed speed exceeds the {MAX_SPEED_KMH} km/h development plausibility threshold."))
                elif limits and speed > min(limits):
                    abnormal.append(self._alert(tid, "SPEED_LIMIT_VIOLATION", "MEDIUM", previous, current, evidence,
                        "Observed speed exceeds configured road-network speed-limit metadata."))
                if route["expected_travel_seconds"] and observed < route["expected_travel_seconds"]:
                    abnormal.append(self._alert(tid, "ABNORMALLY_FAST", "MEDIUM", previous, current, evidence,
                        "Observed time is shorter than network expected travel time."))
                if observed > MAX_GAP_SECONDS:
                    abnormal.append(self._alert(tid, "EXCESSIVE_TRAJECTORY_GAP", "LOW", previous, current, evidence,
                        "Observed gap exceeds the configured continuity window."))
            if len(abnormal) > 1:
                alerts.append(self._alert(tid, "REPEATED_ABNORMAL_MOVEMENT", "CRITICAL", None, None,
                    {"component_alert_ids": [a["anomaly_id"] for a in abnormal]},
                    "Multiple abnormal transitions were consolidated into one stronger alert."))
            alerts.extend(abnormal)
        return self._dedupe(alerts)

    def movement(self, trajectories: Iterable[dict[str, Any]], alerts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        alert_counts = defaultdict(int)
        for alert in alerts: alert_counts[alert["trajectory_id"]] += 1
        results = []
        for item in trajectories:
            events, identity = self._events(item), item["identity"]
            transitions = self._transitions(events)
            distances = [t["route"]["distance_km"] for t in transitions if t["route"]["status"] == "CONNECTED"]
            speeds = [t["speed_kmh"] for t in transitions if t["speed_kmh"] is not None]
            results.append({"trajectory_id": item["trajectory_id"], "included_for_traffic": self._included(item),
                "observation_count": len(events), "camera_count": len(set(e["camera_id"] for e in events)),
                "first_camera": events[0]["camera_id"] if events else None, "last_camera": events[-1]["camera_id"] if events else None,
                "first_time": events[0]["timestamp"] if events else None, "last_time": events[-1]["timestamp"] if events else None,
                "duration_seconds": _seconds(events[0]["timestamp"], events[-1]["timestamp"]) if len(events)>1 else None,
                "total_route_distance_km": sum(distances) if distances else None, "distance_sources": sorted({s for t in transitions for s in t["route"].get("distance_sources", [])}),
                "transition_count": len(transitions), "average_speed_kmh": sum(speeds)/len(speeds) if speeds else None,
                "minimum_speed_kmh": min(speeds) if speeds else None, "maximum_speed_kmh": max(speeds) if speeds else None,
                "anomaly_count": alert_counts[item["trajectory_id"]], "quality_score": identity["quality_score"],
                "quality_level": identity["quality_level"], "usability": identity["usability"], "lifecycle_state": item["lifecycle"]["state"]})
        return results

    def flows(self, trajectories: Iterable[dict[str, Any]], alerts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        alert_keys = {(a["trajectory_id"], tuple(a["event_ids"])) for a in alerts if a["event_ids"]}
        groups: dict[tuple[str,str], list[dict[str,Any]]] = defaultdict(list)
        for item in trajectories:
            if not self._included(item): continue
            for transition in self._transitions(self._events(item)):
                if transition["route"]["status"] == "CONNECTED":
                    transition["trajectory_id"] = item["trajectory_id"]
                    transition["anomaly"] = (item["trajectory_id"], tuple(transition["event_ids"])) in alert_keys
                    groups[(transition["source_camera"], transition["destination_camera"])].append(transition)
        return [self._aggregate_flow(key, value) for key, value in sorted(groups.items())]

    def travel_time(self, flows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        results=[]
        for flow in flows:
            times=flow["travel_times_seconds"]; speeds=flow["speeds_kmh"]; expected=flow.get("expected_travel_seconds")
            avg=sum(times)/len(times); deviation=(avg-expected)/expected if expected else None
            classification="NORMAL" if deviation is None or deviation <= .25 else "SEVERELY_DELAYED" if deviation > 1 else "DELAYED"
            results.append({"source_camera":flow["source_camera"],"destination_camera":flow["destination_camera"],"traversal_count":flow["traversal_count"],"average_travel_seconds":avg,"median_travel_seconds":median(times),"minimum_travel_seconds":min(times),"maximum_travel_seconds":max(times),"average_speed_kmh":sum(speeds)/len(speeds) if speeds else None,"expected_travel_seconds":expected,"travel_time_deviation_ratio":deviation,"classification":classification,"distance_source":flow["distance_sources"]})
        return results

    def congestion(self, flows: Iterable[dict[str, Any]], window_minutes: int=5) -> list[dict[str, Any]]:
        if window_minutes <= 0: raise ValueError("window_minutes must be positive")
        buckets=defaultdict(list)
        for flow in flows:
            for timestamp, speed in zip(flow["start_times"], flow["speeds_kmh"]):
                value=_time(timestamp); minute=(value.minute//window_minutes)*window_minutes
                buckets[(flow["source_camera"],flow["destination_camera"],f"{value.hour:02}:{minute:02}:00")].append(speed)
        return [self._congestion(key, speeds, window_minutes) for key,speeds in sorted(buckets.items())]

    def routes(self, trajectories: Iterable[dict[str, Any]], movements: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id={m["trajectory_id"]:m for m in movements}; groups=defaultdict(list)
        for item in trajectories:
            m=by_id[item["trajectory_id"]]
            if not m["included_for_traffic"] or not m["first_camera"] or m["first_camera"]==m["last_camera"]: continue
            groups[(m["first_camera"],m["last_camera"],tuple(item["identity"]["camera_sequence"]))].append(m)
        return [{"origin_camera":k[0],"destination_camera":k[1],"camera_sequence":list(k[2]),"trajectory_ids":[x["trajectory_id"] for x in v],"trajectory_count":len(v),"average_duration_seconds":sum(x["duration_seconds"] for x in v if x["duration_seconds"] is not None)/len(v),"average_distance_km":sum(x["total_route_distance_km"] or 0 for x in v)/len(v),"anomaly_count":sum(x["anomaly_count"] for x in v)} for k,v in sorted(groups.items())]

    def _events(self,item): return [a["event"] for a in item["associations"] if a.get("event")]
    def _included(self,item): return item["identity"]["usability"]=="ANALYTICS READY" and item["lifecycle"]["state"] in {"ACTIVE","COMPLETED"} and not any(a["status"]=="REVIEW" for a in item["associations"])
    def _transitions(self,events):
        result=[]
        for a,b in zip(events,events[1:]):
            route=self.network.route(a["camera_id"],b["camera_id"]); seconds=_seconds(a["timestamp"],b["timestamp"])
            result.append({"source_camera":a["camera_id"],"destination_camera":b["camera_id"],"event_ids":[a["id"],b["id"]],"start_time":a["timestamp"],"route":route,"travel_seconds":seconds,"speed_kmh":route["distance_km"]/seconds*3600 if route["status"]=="CONNECTED" and seconds>0 else None})
        return result
    def _alert(self,tid,kind,severity,a,b,evidence,explanation):
        ids=[] if not a else [a["id"],b["id"]]; return {"anomaly_id":f"{tid}:{kind}:{'-'.join(map(str,ids))}","trajectory_id":tid,"event_ids":ids,"anomaly_type":kind,"severity":severity,"status":"OPEN","source_camera":a["camera_id"] if a else None,"destination_camera":b["camera_id"] if b else None,"evidence":evidence,"explanation":explanation,"recommended_action":"REVIEW" if severity in {"LOW","MEDIUM"} else "ALERT"}
    def _dedupe(self,alerts): return list({a["anomaly_id"]:a for a in alerts}.values())
    def _aggregate_flow(self,key,items):
        times=[x["travel_seconds"] for x in items]; speeds=[x["speed_kmh"] for x in items if x["speed_kmh"] is not None]; route=items[0]["route"]
        return {"source_camera":key[0],"destination_camera":key[1],"direction":f"{key[0]}->{key[1]}","traversal_count":len(items),"unique_trajectory_count":len({x["trajectory_id"] for x in items}),"first_observed":min(x["start_time"] for x in items),"last_observed":max(x["start_time"] for x in items),"travel_times_seconds":times,"speeds_kmh":speeds,"start_times":[x["start_time"] for x in items],"average_travel_seconds":sum(times)/len(times),"median_travel_seconds":median(times),"average_speed_kmh":sum(speeds)/len(speeds) if speeds else None,"anomaly_count":sum(x["anomaly"] for x in items),"network_distance_km":route["distance_km"],"expected_travel_seconds":route["expected_travel_seconds"],"distance_sources":route.get("distance_sources",[])}
    def _congestion(self,key,speeds,minutes):
        volume=len(speeds); avg=sum(speeds)/volume if speeds else None; t=CONGESTION_THRESHOLDS
        level="FREE_FLOW" if volume<t["light_volume"] and (avg is None or avg>=t["slow_speed_kmh"]) else "SEVERE" if volume>=t["heavy_volume"] or (avg is not None and avg<t["very_slow_speed_kmh"]) else "HEAVY" if volume>=t["moderate_volume"] else "MODERATE" if avg is not None and avg<t["slow_speed_kmh"] else "LIGHT"
        return {"source_camera":key[0],"destination_camera":key[1],"window_start":key[2],"window_minutes":minutes,"traversal_count":volume,"average_speed_kmh":avg,"congestion_level":level,"method":"development_tunable_volume_speed_thresholds"}


def verify_phase8() -> bool:
    pipeline=step_231.run_step_2_30_pipeline(); import tempfile; from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        repo=Phase7TrajectoryRepository(Path(d)/"p.json"); repo.bootstrap(pipeline["identity_records"],pipeline["filtered_events"]); records=repo.query(); service=Phase8Analytics(ProductionCameraNetwork.from_development_graph()); alerts=service.anomalies(records); movement=service.movement(records,alerts); flows=service.flows(records,alerts); travel=service.travel_time(flows); density=service.congestion(flows); routes=service.routes(records,movement)
        checks={"2.38 anomalies":any(a["anomaly_type"]=="UNREALISTIC_SPEED" for a in alerts) and any(a["anomaly_type"]=="IMPOSSIBLE_ROUTE" for a in alerts),"2.39 movement":len(movement)==8 and next(x for x in movement if x["trajectory_id"]=="TRAJ_0001")["total_route_distance_km"] is not None,"2.40 directed flow":all(x["direction"]==f"{x['source_camera']}->{x['destination_camera']}" for x in flows),"2.41 travel":all(x["average_travel_seconds"]>0 for x in travel),"2.42 congestion":all(x["congestion_level"] in {"FREE_FLOW","LIGHT","MODERATE","HEAVY","SEVERE"} for x in density),"2.43 OD":bool(routes),"empty safety":service.flows([],[])==[] and service.congestion([])==[],"2.37 regression":verify_step_2_37()}
    print("\nPHASE 8 VERIFICATION"); [print(f"{k}: {'PASS' if v else 'FAIL'}") for k,v in checks.items()]; return all(checks.values())

if __name__=="__main__": raise SystemExit(0 if verify_phase8() else 1)
