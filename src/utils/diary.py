"""Trade diary for logging AI decisions and trade history."""
import json
from datetime import datetime
from pathlib import Path

class TradeDiary:
    """Persistent log of trading decisions and rationale."""
    
    def __init__(self, filepath: str = "diary.jsonl"):
        """Initialize diary with file path."""
        self.filepath = Path(filepath)
        self.entries = []
        self._load()
    
    def _load(self):
        """Load existing entries from JSONL file."""
        if self.filepath.exists():
            try:
                self.entries = []
                with open(self.filepath, 'r') as f:
                    for line in f:
                        try:
                            self.entries.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Warning: Could not load diary: {e}")
                self.entries = []
        else:
            self.entries = []
    
    def _save(self):
        """Save entries to JSONL file (append mode)."""
        # Note: On n'écrase pas, on append juste la nouvelle entrée
        pass
    
    def log(self, asset: str, action: str, rationale: str, **kwargs):
        """Log a trading decision.
        
        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')
            action: Action taken ('buy', 'sell', 'hold')
            rationale: Reasoning behind the decision
            **kwargs: Additional metadata (price, size, etc.)
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'asset': asset,
            'action': action,
            'rationale': rationale,
            **kwargs
        }
        
        # Append to JSONL file
        try:
            with open(self.filepath, 'a') as f:
                f.write(json.dumps(entry) + '\n')
            self.entries.append(entry)
        except Exception as e:
            print(f"Error saving diary entry: {e}")
    
    def get_recent_entries(self, limit: int = 50):
        """Get the most recent diary entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent entries (newest first)
        """
        return list(reversed(self.entries[-limit:]))
    
    def get_entries_for_asset(self, asset: str, limit: int = 50):
        """Get recent entries for a specific asset.
        
        Args:
            asset: Asset symbol to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of entries for the asset (newest first)
        """
        asset_entries = [e for e in self.entries if e.get('asset') == asset]
        return list(reversed(asset_entries[-limit:]))
    
    def clear(self):
        """Clear all diary entries."""
        self.entries = []
        if self.filepath.exists():
            self.filepath.unlink()
    
    def __len__(self):
        """Return number of entries."""
        return len(self.entries)