import unittest
from unittest.mock import MagicMock, patch
import datetime

# Mock DATABASE_URL environment variable
import os
os.environ["DATABASE_URL"] = "postgresql://mock_user:mock_pass@localhost:5432/mock_db"

import database

class TestDatabase(unittest.TestCase):
    @patch('database.get_connection')
    def test_free_user_quota_reset_on_new_month(self, mock_get_conn):
        # Setup mock database cursor to return free user data
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Row data for a FREE user whose last usage month was 2026-06 (different from current 2026-07)
        mock_cur.fetchone.return_value = {
            'current_mode': 'HUMAN',
            'usage_month': '2026-06',
            'usage_count': 3,
            'purchased_quota': 0,
            'subscription_tier': 'FREE',
            'subscription_expiry': None
        }
        
        # Call get_user_status_data with a new month
        status = database.get_user_status_data("U12345", "2026-07")
        
        # Verify that usage_count is reset to 0 (usage returns 0)
        self.assertEqual(status['usage'], 0)
        
        # Calculate expected write date
        tz_tw = datetime.timezone(datetime.timedelta(hours=8))
        today = datetime.datetime.now(tz_tw)
        if today.strftime('%Y-%m') == "2026-07":
            expected_date = today.strftime('%Y-%m-%d')
        else:
            expected_date = "2026-07-01"

        # Verify that database update was called to reset usage_count and usage_month
        mock_cur.execute.assert_any_call(
            "UPDATE users SET usage_month = %s, usage_count = 0 WHERE user_id = %s",
            (expected_date, "U12345")
        )

    @patch('database.get_connection')
    def test_subscribed_user_quota_no_reset_on_new_month(self, mock_get_conn):
        # Setup mock database cursor to return subscribed user data
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Row data for an ADVANCED user whose last usage month was 2026-06 (different from current 2026-07)
        tz_tw = datetime.timezone(datetime.timedelta(hours=8))
        future_expiry = (datetime.datetime.now(tz_tw) + datetime.timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')
        
        mock_cur.fetchone.return_value = {
            'current_mode': 'HUMAN',
            'usage_month': '2026-06',
            'usage_count': 12,
            'purchased_quota': 0,
            'subscription_tier': 'ADVANCED',
            'subscription_expiry': future_expiry
        }
        
        # Call get_user_status_data with a new month
        status = database.get_user_status_data("U12345", "2026-07")
        
        # Verify that usage_count is NOT reset to 0 (usage returns 12)
        self.assertEqual(status['usage'], 12)
        
        # Calculate expected write date
        tz_tw = datetime.timezone(datetime.timedelta(hours=8))
        today = datetime.datetime.now(tz_tw)
        if today.strftime('%Y-%m') == "2026-07":
            expected_date = today.strftime('%Y-%m-%d')
        else:
            expected_date = "2026-07-01"

        # Verify that only the usage_month is updated without resetting count
        mock_cur.execute.assert_any_call(
            "UPDATE users SET usage_month = %s WHERE user_id = %s",
            (expected_date, "U12345")
        )

if __name__ == '__main__':
    unittest.main()
