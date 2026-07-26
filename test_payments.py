import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock all environment variables before importing app
import os
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "mock_token"
os.environ["LINE_CHANNEL_SECRET"] = "mock_secret"
os.environ["DATABASE_URL"] = "postgresql://mock_user:mock_pass@localhost:5432/mock_db"
os.environ["GEMINI_API_KEY"] = "AIzaSyMockKeyForTesting"

import database
database.get_connection = MagicMock(return_value=None)
database.init_db = MagicMock()

import app

class TestPayments(unittest.TestCase):
    def setUp(self):
        # Create Flask test client
        self.app = app.app.test_client()
        self.app.testing = True

        # Clear mocks before each test
        app.line_bot_api = MagicMock()
        app.database = MagicMock()
        app.newebpay_integration = MagicMock()

    @patch('app.database')
    @patch('app.newebpay_integration')
    def test_newebpay_return_single_point_purchase_1000(self, mock_newebpay, mock_db):
        # Configure decryption mock to return SUCCESS for point10 (NT$ 1000)
        mock_newebpay.decrypt_newebpay_response.return_value = {
            "Status": "SUCCESS",
            "Result": {
                "MerchantOrderNo": "TEST_ORDER_1",
                "Amt": 1000,
                "TradeNo": "26072617484022203",
                "PayTime": "2026-07-26 18:00:00"
            }
        }
        
        # Configure database mocks
        mock_db.get_payment_order.return_value = {
            "user_id": "U12345",
            "plan_id": "point10",
            "amount": 1000
        }
        mock_db.get_user_status_data.return_value = {
            "free_limit": 3,
            "usage": 0,
            "purchased": 50,
            "tier": "FREE"
        }

        # Mock LINE Push message
        mock_push = MagicMock()
        app.line_bot_api.push_message = mock_push

        # Send post request to /newebpay/return
        response = self.app.post("/newebpay/return", data={"TradeInfo": "SOME_HEX"})
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), "OK")

        # 1. Assert that the purchased quota was added correctly: 1000 NT$ -> 100 points
        mock_db.add_purchased_quota.assert_called_once_with("U12345", 100)

        # 2. Assert order status update
        mock_db.update_payment_order_status.assert_called_once_with(
            "TEST_ORDER_1",
            "SUCCESS",
            trade_no="26072617484022203",
            pay_time="2026-07-26 18:00:00",
            amount=1000
        )

        # 3. Assert LINE push was called (and contains the correct warning notice)
        mock_push.assert_called_once()
        sent_text = mock_push.call_args[0][1].text
        self.assertIn("100 次額度已入帳", sent_text)
        self.assertIn("會員方案：FREE", sent_text)

    @patch('app.database')
    @patch('app.newebpay_integration')
    def test_newebpay_return_single_point_purchase_100(self, mock_newebpay, mock_db):
        # Configure decryption mock to return SUCCESS for point10 (NT$ 100)
        mock_newebpay.decrypt_newebpay_response.return_value = {
            "Status": "SUCCESS",
            "Result": {
                "MerchantOrderNo": "TEST_ORDER_1B",
                "Amt": 100,
                "TradeNo": "26072617484022204",
                "PayTime": "2026-07-26 18:00:00"
            }
        }
        
        # Configure database mocks
        mock_db.get_payment_order.return_value = {
            "user_id": "U12345",
            "plan_id": "point10",
            "amount": 100
        }
        mock_db.get_user_status_data.return_value = {
            "free_limit": 3,
            "usage": 0,
            "purchased": 10,
            "tier": "FREE"
        }

        mock_push = MagicMock()
        app.line_bot_api.push_message = mock_push

        response = self.app.post("/newebpay/return", data={"TradeInfo": "SOME_HEX"})
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        # Assert that 100 NT$ -> 10 points
        mock_db.add_purchased_quota.assert_called_once_with("U12345", 10)

    @patch('app.database')
    @patch('app.newebpay_integration')
    def test_newebpay_period_return_basic_single(self, mock_newebpay, mock_db):
        mock_newebpay.decrypt_newebpay_period_response.return_value = {
            "Status": "SUCCESS",
            "Result": {
                "MerchantOrderNo": "TEST_ORDER_2",
                "Amt": 88,
                "AuthAmt": 88,
                "TradeNo": "TRADE_SUB_BASIC",
                "AuthTime": "2026-07-26 18:00:00",
                "Extday": "2026-08-26"
            }
        }
        
        mock_db.get_payment_order.return_value = {
            "user_id": "U67890",
            "plan_id": "basic_single",
            "amount": 88
        }
        mock_db.get_user_status_data.return_value = {
            "free_limit": 8,
            "usage": 0,
            "purchased": 0,
            "tier": "BASIC"
        }

        mock_push = MagicMock()
        app.line_bot_api.push_message = mock_push

        response = self.app.post("/newebpay/period_return", data={"Period": "SOME_HEX"})
        
        self.assertEqual(response.status_code, 200)

        # Assert correct subscription update (with clean date-based expiry_str)
        mock_db.update_subscription.assert_called_once_with("U67890", "BASIC", "2026-08-26 23:59:59")
        
        # Assert status update
        mock_db.update_payment_order_status.assert_called_once_with(
            "TEST_ORDER_2",
            "SUCCESS",
            trade_no="TRADE_SUB_BASIC",
            pay_time="2026-07-26 18:00:00",
            amount=88
        )

        # Assert correct warning message push
        mock_push.assert_called_once()
        sent_text = mock_push.call_args[0][1].text
        self.assertIn("小資玩家", sent_text)
        self.assertIn("【重要提醒】系統限制每位用戶只能訂閱「一個」包月方案", sent_text)

    @patch('app.database')
    @patch('app.newebpay_integration')
    def test_newebpay_period_return_advanced_single(self, mock_newebpay, mock_db):
        mock_newebpay.decrypt_newebpay_period_response.return_value = {
            "Status": "SUCCESS",
            "Result": {
                "MerchantOrderNo": "TEST_ORDER_3",
                "Amt": 399,
                "AuthAmt": 399,
                "TradeNo": "TRADE_SUB_ADVANCED",
                "AuthTime": "2026-07-26 18:00:00",
                "Extday": "2026-08-26"
            }
        }
        
        mock_db.get_payment_order.return_value = {
            "user_id": "U67890",
            "plan_id": "advanced_single",
            "amount": 399
        }
        mock_db.get_user_status_data.return_value = {
            "free_limit": 50,
            "usage": 0,
            "purchased": 10,
            "tier": "ADVANCED"
        }

        mock_push = MagicMock()
        app.line_bot_api.push_message = mock_push

        response = self.app.post("/newebpay/period_return", data={"Period": "SOME_HEX"})
        
        self.assertEqual(response.status_code, 200)

        mock_db.update_subscription.assert_called_once_with("U67890", "ADVANCED", "2026-08-26 23:59:59")
        
        mock_push.assert_called_once()
        sent_text = mock_push.call_args[0][1].text
        self.assertIn("進階藏家", sent_text)
        self.assertIn("【重要提醒】系統限制每位用戶只能訂閱「一個」包月方案", sent_text)

    @patch('app.database')
    @patch('app.newebpay_integration')
    def test_newebpay_period_return_business_single(self, mock_newebpay, mock_db):
        mock_newebpay.decrypt_newebpay_period_response.return_value = {
            "Status": "SUCCESS",
            "Result": {
                "MerchantOrderNo": "TEST_ORDER_4",
                "Amt": 860,
                "AuthAmt": 860,
                "TradeNo": "TRADE_SUB_BUSINESS",
                "AuthTime": "2026-07-26 18:00:00",
                "Extday": "2026-08-26"
            }
        }
        
        mock_db.get_payment_order.return_value = {
            "user_id": "U67890",
            "plan_id": "business_single",
            "amount": 860
        }
        mock_db.get_user_status_data.return_value = {
            "free_limit": 150,
            "usage": 0,
            "purchased": 0,
            "tier": "BUSINESS"
        }

        mock_push = MagicMock()
        app.line_bot_api.push_message = mock_push

        response = self.app.post("/newebpay/period_return", data={"Period": "SOME_HEX"})
        
        self.assertEqual(response.status_code, 200)

        mock_db.update_subscription.assert_called_once_with("U67890", "BUSINESS", "2026-08-26 23:59:59")
        
        mock_push.assert_called_once()
        sent_text = mock_push.call_args[0][1].text
        self.assertIn("商務旗艦", sent_text)
        self.assertIn("【重要提醒】系統限制每位用戶只能訂閱「一個」包月方案", sent_text)

if __name__ == '__main__':
    unittest.main()
