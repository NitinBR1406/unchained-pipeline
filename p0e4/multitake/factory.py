"""MULTI_TAKE_RAW_DROP_V01 deterministic contract implementation.

No external agent, Resolve, production watcher, or publication API is callable here.
The module validates byte-bound evidence and prepares execution contracts only.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def _sha(value):
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "sha256")


def _governance(value):
    require(value == {"production_deployment_authorized": False, "publication_authorized": False,
                      "first_real_poster": "PAUSED_BY_NITIN"}, "governance")


class MultiTakeFactory:
    CONFIDENCE_MIN = 850
    DRIFT_PPM_MAX = 80
    MAX_DERIVATIVES = 4

    def ingest(self, manifest, blobs):
        require(manifest.get("schema") == "MULTI_TAKE_RAW_DROP_V01", "manifest schema")
        require(manifest.get("scope") == "SYNTHETIC_DISPOSABLE_ONLY", "real RAW drop forbidden")
        _governance(manifest.get("governance"))
        assets = manifest.get("assets")
        require(isinstance(assets, list), "assets")
        takes = [a for a in assets if a.get("role") == "TAKE"]
        masters = [a for a in assets if a.get("role") == "MASTER_AUDIO"]
        require(len(takes) >= 2 and len(masters) == 1, "takes/master cardinality")
        require(all(a.get("role") in ("TAKE", "MASTER_AUDIO", "PHOTO") for a in assets), "asset role")
        seen_ids = set(); unique = {}; accepted = []; aliases = []
        for asset in assets:
            require(set(asset) == {"asset_id", "role", "source_uri", "sha256", "bytes"}, "asset fields")
            require(asset["asset_id"] not in seen_ids, "duplicate asset id"); seen_ids.add(asset["asset_id"])
            _sha(asset["sha256"]); blob = blobs.get(asset["source_uri"])
            require(isinstance(blob, bytes) and blob, "source bytes unavailable")
            require(len(blob) == asset["bytes"] and digest(blob) == asset["sha256"], "source drift")
            if asset["sha256"] in unique:
                aliases.append({"asset_id": asset["asset_id"], "canonical_asset_id": unique[asset["sha256"]],
                                "sha256": asset["sha256"], "status": "DUPLICATE_SUPPRESSED"})
            else:
                unique[asset["sha256"]] = asset["asset_id"]; accepted.append(deepcopy(asset))
        require(len([a for a in accepted if a["role"] == "TAKE"]) >= 2, "insufficient unique takes")
        result = {"schema": "MULTI_FILE_INGEST_RECEIPT_V01", "manifest_sha256": digest(manifest),
                  "accepted": accepted, "aliases": aliases, "status": "GREEN_SYNTHETIC_ONLY",
                  "filename_semantics_used": False, "governance": manifest["governance"]}
        result["receipt_sha256"] = digest(result)
        return result

    def probe(self, ingest, probes):
        take_assets = {a["asset_id"]: a for a in ingest["accepted"] if a["role"] == "TAKE"}
        require(set(probes) == set(take_assets), "probe coverage")
        out = []
        for asset_id in sorted(take_assets):
            p = probes[asset_id]
            require(set(p) == {"duration_ms", "fps_num", "fps_den", "width", "height", "orientation",
                               "guide_audio_present", "full_decode"}, "probe fields")
            require(p["duration_ms"] > 0 and p["fps_num"] > 0 and p["fps_den"] > 0, "probe timing")
            require(p["width"] > 0 and p["height"] > 0 and p["orientation"] in ("LANDSCAPE", "PORTRAIT", "SQUARE"), "probe geometry")
            require(p["guide_audio_present"] is True and p["full_decode"] is True, "guide audio/decode")
            out.append({"asset_id": asset_id, "take_sha256": take_assets[asset_id]["sha256"], **deepcopy(p),
                        "normalization": {"output_width": 1080, "output_height": 1920, "output_fps_num": 30,
                                          "output_fps_den": 1, "method": "SCALE_PAD_OR_EVIDENCE_CROP",
                                          "frame_rate_conform": (p["fps_num"], p["fps_den"]) != (30, 1)}})
        return {"schema": "MULTI_TAKE_TECHNICAL_PROBE_V01", "takes": out, "status": "GREEN",
                "probe_sha256": digest(out)}

    def bind_master_audio(self, ingest):
        master = [a for a in ingest["accepted"] if a["role"] == "MASTER_AUDIO"]
        require(len(master) == 1, "authoritative audio")
        return {"schema": "MASTER_AUDIO_BINDING_V01", "asset_id": master[0]["asset_id"],
                "sha256": master[0]["sha256"], "source_uri": master[0]["source_uri"],
                "final_programme_audio": "AUTHORITATIVE_MASTER_ONLY", "take_audio_use": "SYNC_EVIDENCE_ONLY",
                "status": "GREEN"}

    def align(self, probe, observations):
        take_map = {t["asset_id"]: t for t in probe["takes"]}
        require(set(observations) == set(take_map), "alignment coverage")
        rows = []
        for asset_id in sorted(take_map):
            o = observations[asset_id]
            require(set(o) == {"method", "offset_ms", "drift_ppm", "confidence_milli", "usable_start_ms",
                               "usable_end_ms", "anchor_count", "evidence_sha256"}, "alignment fields")
            require(o["method"] == "CAMERA_GUIDE_AUDIO_CORRELATION", "alignment method")
            _sha(o["evidence_sha256"])
            reasons = []
            if o["confidence_milli"] < self.CONFIDENCE_MIN: reasons.append("LOW_CONFIDENCE")
            if abs(o["drift_ppm"]) > self.DRIFT_PPM_MAX: reasons.append("MATERIAL_DRIFT")
            if o["anchor_count"] < 3: reasons.append("INSUFFICIENT_ANCHORS")
            if not (0 <= o["usable_start_ms"] < o["usable_end_ms"] <= take_map[asset_id]["duration_ms"]): reasons.append("INVALID_USABLE_RANGE")
            rows.append({"asset_id": asset_id, "take_sha256": take_map[asset_id]["take_sha256"], **deepcopy(o),
                         "status": "READY" if not reasons else "HOLD", "hold_reasons": reasons})
        return {"schema": "PER_TAKE_LIPSYNC_ALIGNMENT_V01", "takes": rows,
                "status": "GREEN" if all(r["status"] == "READY" for r in rows) else "HOLD_ALIGNMENT_REVIEW",
                "thresholds": {"confidence_milli_min": self.CONFIDENCE_MIN, "abs_drift_ppm_max": self.DRIFT_PPM_MAX,
                               "anchor_count_min": 3}, "alignment_sha256": digest(rows)}

    def synchronized_set(self, probe, alignment, audio):
        require(alignment["status"] == "GREEN", "alignment not accepted")
        rows = []
        probes = {p["asset_id"]: p for p in probe["takes"]}
        for row in alignment["takes"]:
            rows.append({**deepcopy(row), "technical_probe": deepcopy(probes[row["asset_id"]]),
                         "guide_audio_final_mix": False})
        result = {"schema": "SYNCHRONIZED_TAKE_SET_V01", "takes": rows, "master_audio": deepcopy(audio),
                  "programme_audio_sha256": audio["sha256"], "status": "GREEN", "filename_order_used": False}
        result["set_sha256"] = digest(result)
        return result

    def validate_intelligence(self, sync_set, intelligence):
        require(intelligence.get("schema") == "GEMINI_MULTI_TAKE_PERFORMANCE_INTELLIGENCE_V01", "intelligence schema")
        require(intelligence.get("synchronized_take_set_sha256") == sync_set["set_sha256"], "intelligence binding")
        require(intelligence.get("agent_isolation") == "INDEPENDENT_NO_CLAUDE_OR_CHATGPT_CONCLUSIONS", "agent isolation")
        take_ids = {t["asset_id"] for t in sync_set["takes"]}
        require(set(x["asset_id"] for x in intelligence.get("take_observations", [])) == take_ids, "intelligence coverage")
        for x in intelligence["take_observations"]:
            require(set(x) == {"asset_id", "ranges", "evidence_sha256"}, "intelligence observation fields"); _sha(x["evidence_sha256"])
            require(x["ranges"] and all(set(r) == {"start_ms", "end_ms", "performance_score_milli", "reason_code"}
                                        and r["start_ms"] < r["end_ms"] for r in x["ranges"]), "intelligence ranges")
        require(intelligence.get("lyrics_or_captions_invented") is False, "invented text")
        result = deepcopy(intelligence); result["status"] = "VALIDATED_CONTRACT_ONLY"; result["intelligence_sha256"] = digest(intelligence)
        return result

    def validate_edl(self, sync_set, intelligence, edl):
        require(edl.get("schema") == "MULTI_TAKE_EDIT_DECISION_LIST_V01", "edl schema")
        require(edl.get("synchronized_take_set_sha256") == sync_set["set_sha256"], "edl sync binding")
        require(edl.get("intelligence_sha256") == intelligence["intelligence_sha256"], "edl intelligence binding")
        require(edl.get("filename_semantics_used") is False, "filename inference")
        takes = {t["asset_id"]: t for t in sync_set["takes"]}; segments = edl.get("segments", [])
        require(segments, "segments"); cursor = 0; visible = 0
        for s in segments:
            require(set(s) == {"segment_id", "take_asset_id", "timeline_start_ms", "timeline_end_ms", "take_start_ms",
                               "take_end_ms", "performer_visible", "evidence_sha256", "reason_code"}, "segment fields")
            require(s["take_asset_id"] in takes and s["timeline_start_ms"] == cursor and s["timeline_end_ms"] > cursor, "edl continuity")
            take = takes[s["take_asset_id"]]
            require(take["usable_start_ms"] <= s["take_start_ms"] < s["take_end_ms"] <= take["usable_end_ms"], "outside usable range")
            require(s["take_end_ms"] - s["take_start_ms"] == s["timeline_end_ms"] - s["timeline_start_ms"], "segment duration")
            _sha(s["evidence_sha256"]); cursor = s["timeline_end_ms"]
            if s["performer_visible"]: visible += s["timeline_end_ms"] - s["timeline_start_ms"]
        require(visible * 5 >= cursor * 4, "80_PERCENT_PERFORMANCE_RULE")
        derivatives = edl.get("derivatives", [])
        require(len(derivatives) <= self.MAX_DERIVATIVES and len({d["derivative_id"] for d in derivatives}) == len(derivatives), "derivative limit/ids")
        for d in derivatives:
            require(set(d) == {"derivative_id", "start_ms", "end_ms", "platform", "performer_visible_ms"}, "derivative fields")
            require(0 <= d["start_ms"] < d["end_ms"] <= cursor and d["performer_visible_ms"] * 5 >= (d["end_ms"]-d["start_ms"])*4, "derivative rule")
        result = deepcopy(edl); result.update(status="GREEN_MACHINE_READABLE", duration_ms=cursor, visible_performance_ms=visible)
        result["edl_sha256"] = digest(result)
        return result

    def validate_production_contract(self, edl, contract):
        require(contract.get("schema") == "MULTI_TAKE_PRODUCTION_TRANSLATION_V01", "production schema")
        require(contract.get("edl_sha256") == edl["edl_sha256"], "production binding")
        require(contract.get("mode") == "PLAN_ONLY_NO_EXTERNAL_EXECUTION", "execution mode")
        require(contract.get("final_audio_route") == "AUTHORITATIVE_MASTER_ONLY" and contract.get("guide_audio_muted") is True, "audio route")
        require(set(contract.get("color", {})) == {"normalization", "shot_match", "creative_look"}, "color stages must remain separate")
        allowed = {"cut", "reframe", "zoom", "push_in", "shake", "transition", "effect", "title", "caption"}
        effect_ms = 0
        for op in contract.get("operations", []):
            require(set(op) == {"operation_id", "kind", "start_ms", "end_ms", "evidence_sha256", "parameters"}, "operation fields")
            require(op["kind"] in allowed and 0 <= op["start_ms"] < op["end_ms"] <= edl["duration_ms"], "operation")
            _sha(op["evidence_sha256"])
            if op["kind"] in ("caption", "title"):
                require(op["parameters"].get("authoritative_text_ref_sha256"), "authoritative text required")
                _sha(op["parameters"]["authoritative_text_ref_sha256"])
            if op["kind"] in ("shake", "transition", "effect"): effect_ms += op["end_ms"] - op["start_ms"]
        require(effect_ms * 4 <= edl["duration_ms"], "excessive effects plan")
        result = deepcopy(contract); result["status"] = "VALIDATED_PLAN_ONLY"; result["translation_sha256"] = digest(contract)
        return result

    QC_CATEGORIES = ("sync_defects", "bad_cuts", "framing_crop", "excessive_effects", "color_mismatch",
                     "audio_defects", "caption_safe_area", "technical_decode", "performance_rule")

    def qc(self, output_sha256, report):
        _sha(output_sha256); require(set(report) == set(self.QC_CATEGORIES), "qc coverage")
        require(all(v in ("PASS", "FAIL") for v in report.values()), "qc verdict")
        failed = [k for k in self.QC_CATEGORIES if report[k] != "PASS"]
        return {"schema": "MULTI_TAKE_OUTPUT_QC_V01", "output_sha256": output_sha256, "checks": deepcopy(report),
                "failed": failed, "status": "ACCEPTED" if not failed else "REPAIR_REQUIRED",
                "independent_gemini_re_qc_required_after_repair": bool(failed)}

    def repair(self, original_sha256, repaired_sha256, attempt, source_set_sha256, re_qc):
        _sha(original_sha256); _sha(repaired_sha256); _sha(source_set_sha256)
        require(1 <= attempt <= 2, "repair budget"); require(original_sha256 != repaired_sha256, "repair output unchanged")
        require(re_qc["output_sha256"] == repaired_sha256 and re_qc["status"] == "ACCEPTED", "independent re-QC required")
        return {"schema": "BOUNDED_REPAIR_RERENDER_V01", "original_sha256": original_sha256,
                "repaired_sha256": repaired_sha256, "source_set_sha256": source_set_sha256, "attempt": attempt,
                "source_rebinding_allowed": False, "status": "GREEN_AFTER_RE_QC"}
