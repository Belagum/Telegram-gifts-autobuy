from flask import Blueprint, jsonify

bp_misc = Blueprint("misc", __name__)

@bp_misc.get("/api/health")
def health(): return jsonify({"ok": True})
