"""Student prediction persistence and live dashboard queries."""
from pymongo.errors import PyMongoError
from flask import current_app

from ..extensions import mongo_database, mongo_configured
from ..services.errors import StorageUnavailable
from .json_store import read_list, write_list


def _public(doc):
    row = dict(doc)
    if "_id" in row:
        row["id"] = str(row.pop("_id"))
    return row


class StudentRepository:
    _indexes_ready = False

    def _db(self):
        if not mongo_configured():
            return None
        try:
            db = mongo_database()
            if not self._indexes_ready:
                db.students.create_index([("created_at", -1)])
                db.students.create_index([("user_id", 1), ("created_at", -1)])
                self.__class__._indexes_ready = True
            return db
        except PyMongoError as exc:
            raise StorageUnavailable() from exc

    def create(self, student):
        db = self._db()
        if db is not None:
            try:
                db.students.insert_one(student)
            except PyMongoError as exc:
                raise StorageUnavailable() from exc
            return
        path = current_app.config["STUDENTS_PATH"]
        rows = read_list(path)
        rows.insert(0, student)
        write_list(path, rows[:10000])

    def list_for_user(self, user, limit=500):
        db = self._db()
        if db is not None:
            query = {} if user["role"] == "admin" else {"user_id": user["id"]}
            try:
                return [_public(doc) for doc in db.students.find(query).sort("created_at", -1).limit(limit)]
            except PyMongoError as exc:
                raise StorageUnavailable() from exc
        rows = read_list(current_app.config["STUDENTS_PATH"])
        if user["role"] != "admin":
            rows = [r for r in rows if r.get("user_id") == user["id"]]
        return rows[:limit]

    def dashboard_summary(self):
        db = self._db()
        if db is not None:
            try:
                total = db.students.count_documents({})
                placed = db.students.count_documents({"prediction": "Placed"})
                monthly = list(db.students.aggregate([
                    {"$group": {"_id": {"year": {"$year": {"$toDate": "$created_at"}}, "month": {"$month": {"$toDate": "$created_at"}}}, "total": {"$sum": 1}, "placed": {"$sum": {"$cond": [{"$eq": ["$prediction", "Placed"]}, 1, 0]}}}},
                    {"$sort": {"_id.year": 1, "_id.month": 1}},
                    {"$limit": 12},
                ]))
                recent = [_public(row) for row in db.students.find().sort("created_at", -1).limit(5)]
                names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                monthly = [{"month": names[row["_id"]["month"] - 1], "total": row["total"], "placed": row["placed"]} for row in monthly]
                return {"total": total, "placed": placed, "monthly": monthly, "recent": recent}
            except PyMongoError as exc:
                raise StorageUnavailable() from exc
        rows = read_list(current_app.config["STUDENTS_PATH"])
        from collections import defaultdict
        buckets = defaultdict(lambda: {"total": 0, "placed": 0, "month": ""})
        for row in rows:
            try:
                from datetime import datetime
                date = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                key = date.strftime("%Y-%m")
                buckets[key]["month"] = date.strftime("%b")
                buckets[key]["total"] += 1
                buckets[key]["placed"] += row.get("prediction") == "Placed"
            except (KeyError, TypeError, ValueError):
                continue
        return {"total": len(rows), "placed": sum(row.get("prediction") == "Placed" for row in rows), "monthly": [buckets[key] for key in sorted(buckets)[-12:]], "recent": rows[:5]}
