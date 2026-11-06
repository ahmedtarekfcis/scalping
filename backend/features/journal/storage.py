import os
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Locate root directory and data folder
# storage.py is at: <repo_root>/backend/features/journal/storage.py
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]

DATA_DIR = _REPO_ROOT / "data"
JOURNAL_FILE = DATA_DIR / "journal_trades.json"
BACKUP_FILE = DATA_DIR / "journal_trades.bak.json"


class JournalStorageEngine:
    """
    Manages reading, writing, updating, and backing up journal trades in a local JSON file.
    All disk writes are atomic to prevent any data loss or file corruption.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or JOURNAL_FILE
        self.backup_path = self.file_path.with_name(f"{self.file_path.stem}.bak.json")
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the target directory exists."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.file_path.exists():
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write("[]\n")
        except Exception as e:
            logger.error(f"Failed to create data directory/file: {e}")

    def get_file_info(self) -> Dict[str, Any]:
        """Return metadata about the journal JSON file."""
        exists = self.file_path.exists()
        size_bytes = 0
        last_modified = None
        count = 0

        if exists:
            try:
                stat = self.file_path.stat()
                size_bytes = stat.st_size
                last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
                count = len(self.read_trades())
            except Exception as e:
                logger.warning(f"Error getting file stat: {e}")

        return {
            "filePath": str(self.file_path.resolve()),
            "fileName": self.file_path.name,
            "exists": exists,
            "sizeBytes": size_bytes,
            "lastModified": last_modified,
            "tradeCount": count,
        }

    def read_trades(self) -> List[Dict[str, Any]]:
        """
        Safely read all trades from the JSON file.
        Returns a list of trade dictionaries.
        """
        self._ensure_directory()

        if not self.file_path.exists():
            return []

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                data = json.loads(content)

            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "trades" in data and isinstance(data["trades"], list):
                return data["trades"]
            else:
                logger.warning(f"Unexpected JSON format in {self.file_path}, expected list.")
                return []

        except json.JSONDecodeError as err:
            logger.error(f"JSONDecodeError reading {self.file_path}: {err}")
            # Try recovering from backup file if available
            if self.backup_path.exists():
                try:
                    logger.info("Attempting recovery from backup file...")
                    with open(self.backup_path, "r", encoding="utf-8") as bf:
                        backup_data = json.loads(bf.read())
                        if isinstance(backup_data, list):
                            return backup_data
                except Exception as berr:
                    logger.error(f"Backup recovery also failed: {berr}")

            # Archive the corrupted file so user never loses their data completely
            corrupted_archive = self.file_path.with_name(
                f"{self.file_path.stem}.corrupted_{int(datetime.now().timestamp())}.json"
            )
            try:
                shutil.copy2(self.file_path, corrupted_archive)
                logger.info(f"Archived corrupted JSON file to {corrupted_archive}")
            except Exception:
                pass

            return []

        except Exception as e:
            logger.error(f"Error reading journal file {self.file_path}: {e}")
            return []

    def write_trades(self, trades: List[Dict[str, Any]]) -> bool:
        """
        Atomically write trades to the JSON file using a temp file and atomic rename.
        Also maintains an automatic backup file (.bak.json).
        """
        if not isinstance(trades, list):
            logger.error(f"write_trades expected list, got {type(trades)}")
            return False

        # Filter out None entries and ensure demo trades are not preserved unless desired
        clean_trades = [t for t in trades if isinstance(t, dict) and not str(t.get("id", "")).startswith("demo-")]

        temp_file = self.file_path.with_name(f"{self.file_path.name}.tmp")

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # 1. Write to temporary file with clean indenting for easy reading and manual editing
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(clean_trades, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # 2. Update backup copy if target exists
            if self.file_path.exists():
                try:
                    shutil.copy2(self.file_path, self.backup_path)
                except Exception as be:
                    logger.warning(f"Could not write backup file: {be}")

            # 3. Atomic replace
            os.replace(temp_file, self.file_path)
            return True

        except Exception as e:
            logger.error(f"Failed to write journal trades atomically: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            return False

    def upsert_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add or update a single trade in the JSON file.
        """
        if not isinstance(trade, dict) or not trade.get("id"):
            raise ValueError("Trade must be a dict with an 'id' property.")

        trades = self.read_trades()
        target_id = str(trade["id"]).strip()

        index = -1
        for i, existing in enumerate(trades):
            if isinstance(existing, dict) and str(existing.get("id", "")).strip() == target_id:
                index = i
                break

        now_iso = datetime.now().isoformat()
        if index >= 0:
            updated = {**trades[index], **trade, "updatedAt": now_iso}
            trades[index] = updated
            saved_trade = updated
        else:
            if "createdAt" not in trade:
                trade["createdAt"] = now_iso
            trades.insert(0, trade)
            saved_trade = trade

        self.write_trades(trades)
        return saved_trade

    def delete_trade(self, trade_id: str) -> bool:
        """
        Delete a single trade by its id.
        """
        target_id = str(trade_id).strip()
        trades = self.read_trades()
        initial_len = len(trades)
        filtered = [t for t in trades if isinstance(t, dict) and str(t.get("id", "")).strip() != target_id]

        if len(filtered) != initial_len:
            return self.write_trades(filtered)
        return True

    def clear_all(self) -> bool:
        """
        Clear all trades, archiving current content first.
        """
        if self.file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = self.file_path.with_name(f"{self.file_path.stem}.cleared_{timestamp}.json")
            try:
                shutil.copy2(self.file_path, archive_file)
                logger.info(f"Archived trades before clear to {archive_file}")
            except Exception as e:
                logger.warning(f"Could not create clear archive: {e}")

        return self.write_trades([])


# Global default instance
journal_engine = JournalStorageEngine()

