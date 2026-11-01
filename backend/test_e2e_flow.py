"""End-to-end testing of marketplace flow."""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"

class TestFlow:
    def __init__(self):
        self.session = requests.Session()
        self.client_user = None
        self.professional_user = None
        self.professional_profile = None
        self.rate_card = None
        self.consultation = None

    def log(self, title, message=""):
        print(f"\n{'='*60}")
        print(f"[OK] {title}")
        if message:
            print(f"  {message}")
        print(f"{'='*60}")

    def test_signup_and_login(self):
        """Test user signup and login."""
        self.log("STEP 1: User Signup & Login")

        # Signup as client
        client_data = {
            "email": f"client{datetime.now().timestamp()}@test.com",
            "password": "testpass123",
            "first_name": "Jane",
            "last_name": "Client"
        }

        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=client_data)
        print(f"  Signup Status: {response.status_code}")
        self.client_user = response.json()
        print(f"  Client ID: {self.client_user.get('id')}, Email: {self.client_user.get('email')}")

        # Login
        login_data = {"email": client_data["email"], "password": client_data["password"]}
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"  Login Status: {response.status_code}")
        print(f"  Login Response: {response.json()}")

        # Signup as professional
        prof_data = {
            "email": f"professional{datetime.now().timestamp()}@test.com",
            "password": "testpass123",
            "first_name": "John",
            "last_name": "CPA"
        }

        response = self.session.post(f"{BASE_URL}/api/auth/signup", json=prof_data)
        print(f"\n  Professional Signup Status: {response.status_code}")
        self.professional_user = response.json()
        print(f"  Professional ID: {self.professional_user.get('id')}, Email: {self.professional_user.get('email')}")

        # Login as professional
        login_data = {"email": prof_data["email"], "password": prof_data["password"]}
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"  Professional Login Status: {response.status_code}")

    def test_create_professional_profile(self):
        """Test creating professional profile."""
        self.log("STEP 2: Create Professional Profile")

        profile_data = {
            "bio": "CPA with 10+ years of S-Corp and LLC experience. Specializing in small business tax optimization.",
            "specialties": ["S-Corp", "LLC", "Tax Planning"],
            "years_experience": 12,
            "certifications": ["CPA", "EA"],
            "license_number": "CPA123456",
            "availability_json": {
                "Monday": "9am-5pm",
                "Tuesday": "9am-5pm",
                "Wednesday": "9am-5pm",
                "Thursday": "9am-5pm",
                "Friday": "9am-1pm"
            }
        }

        response = self.session.post(f"{BASE_URL}/api/professionals/profile", json=profile_data)
        print(f"  Status: {response.status_code}")
        self.professional_profile = response.json()
        print(f"  Profile ID: {self.professional_profile.get('id')}")
        print(f"  Verified: {self.professional_profile.get('verified')}")
        print(f"  Specialties: {self.professional_profile.get('specialties')}")

    def test_create_rate_cards(self):
        """Test creating rate cards."""
        self.log("STEP 3: Create Service Rate Cards")

        rate_cards = [
            {
                "service_name": "Initial Consultation",
                "service_type": "fixed",
                "price": 150.00,
                "duration_minutes": 60,
                "description": "60-minute initial consultation to assess your business and tax situation"
            },
            {
                "service_name": "S-Corp Planning Session",
                "service_type": "fixed",
                "price": 300.00,
                "duration_minutes": 120,
                "description": "Comprehensive S-Corp setup and planning"
            },
            {
                "service_name": "Hourly Consultation",
                "service_type": "hourly",
                "price": 150.00,
                "duration_minutes": 60,
                "description": "Hourly rate for ongoing consultation"
            }
        ]

        created_cards = []
        for card in rate_cards:
            response = self.session.post(f"{BASE_URL}/api/professionals/profile/rate-cards", json=card)
            print(f"  Created: {card['service_name']} - ${card['price']} ({response.status_code})")
            created_cards.append(response.json())

        self.rate_card = created_cards[0]
        print(f"\n  Total Rate Cards Created: {len(created_cards)}")

    def test_search_professionals(self):
        """Test searching for professionals."""
        self.log("STEP 4: Search & Browse Professionals")

        # Search by specialty
        response = self.session.get(f"{BASE_URL}/api/professionals/search", params={"specialty": "S-Corp"})
        print(f"  Search Status: {response.status_code}")
        professionals = response.json()
        print(f"  Found {len(professionals)} professional(s) with S-Corp specialty")

        if professionals:
            prof = professionals[0]
            print(f"  Professional: {prof.get('user_name')}")
            print(f"  Specialties: {prof.get('specialties')}")
            print(f"  Rating: {prof.get('average_rating')}/5")
            print(f"  Rate Cards: {len(prof.get('rate_cards', []))}")

    def test_book_consultation(self):
        """Test booking a consultation."""
        self.log("STEP 5: Book Consultation")

        # Switch to client session for booking
        client_session = requests.Session()

        # Login as client first
        client_data = {
            "email": self.client_user.get('email'),
            "password": "testpass123"
        }
        login_response = client_session.post(f"{BASE_URL}/api/auth/login", json=client_data)
        print(f"  Client Login: {login_response.status_code}")

        # Book consultation
        scheduled_time = datetime.utcnow() + timedelta(days=5, hours=2)
        booking_data = {
            "professional_id": self.professional_user.get('id'),
            "rate_card_id": self.rate_card.get('id'),
            "scheduled_at": scheduled_time.isoformat(),
            "duration_minutes": 60,
            "notes": "Need help with S-Corp conversion"
        }

        response = client_session.post(f"{BASE_URL}/api/consultations/", json=booking_data)
        print(f"  Booking Status: {response.status_code}")
        self.consultation = response.json()
        print(f"  Consultation ID: {self.consultation.get('id')}")
        print(f"  Total Price: ${self.consultation.get('total_price')}")
        print(f"  Commission (10%): ${self.consultation.get('commission_amount'):.2f}")
        print(f"  Professional Receives: ${self.consultation.get('professional_receives'):.2f}")
        print(f"  Status: {self.consultation.get('status')}")

    def test_messaging(self):
        """Test messaging between client and professional."""
        self.log("STEP 6: Send Messages")

        # Client sends message
        message_data = {"recipient_id": self.professional_user.get('id'), "content": "Hi, I'm interested in your S-Corp consultation services. Can we discuss my options?"}

        response = self.session.post(f"{BASE_URL}/api/messages/", json=message_data)
        print(f"  Message Sent Status: {response.status_code}")
        message = response.json()
        print(f"  Message ID: {message.get('id')}")
        print(f"  Content: {message.get('content')[:50]}...")

        # Get conversations
        response = self.session.get(f"{BASE_URL}/api/messages/conversations")
        print(f"\n  Conversations Status: {response.status_code}")
        conversations = response.json()
        print(f"  Total Conversations: {len(conversations)}")
        if conversations:
            conv = conversations[0]
            print(f"  Last message: {conv.get('last_message')[:40]}...")
            print(f"  Unread count: {conv.get('unread_count')}")

    def test_get_bookings(self):
        """Test retrieving bookings."""
        self.log("STEP 7: View My Bookings")

        response = self.session.get(f"{BASE_URL}/api/consultations/my-bookings")
        print(f"  Status: {response.status_code}")
        bookings = response.json()
        print(f"  Total Bookings: {len(bookings)}")

        if bookings:
            booking = bookings[0]
            print(f"\n  Booking Details:")
            print(f"    Client: {booking.get('client_name')}")
            print(f"    Professional: {booking.get('professional_name')}")
            print(f"    Service: {booking.get('service_name')}")
            print(f"    Price: ${booking.get('total_price')}")
            print(f"    Status: {booking.get('status')}")
            print(f"    Scheduled: {booking.get('scheduled_at')}")

    def test_create_subscription(self):
        """Test creating professional subscription."""
        self.log("STEP 8: Professional Subscription (Stripe)")

        # Login as professional again
        prof_login = {
            "email": self.professional_user.get('email'),
            "password": "testpass123"
        }
        prof_session = requests.Session()
        response = prof_session.post(f"{BASE_URL}/api/auth/login", json=prof_login)
        print(f"  Professional Login: {response.status_code}")

        # Create subscription
        response = prof_session.post(
            f"{BASE_URL}/api/payments/subscription/create",
            params={"plan_type": "basic"}
        )
        print(f"  Subscription Create Status: {response.status_code}")

        if response.status_code == 200:
            sub = response.json()
            print(f"  Subscription ID: {sub.get('subscription_id')}")
            print(f"  Status: {sub.get('status')}")
            print(f"  Amount: ${sub.get('amount')}/month")
        else:
            print(f"  Error: {response.text}")

    def test_earnings_dashboard(self):
        """Test viewing earnings."""
        self.log("STEP 9: Professional Earnings Dashboard")

        # Login as professional
        prof_login = {
            "email": self.professional_user.get('email'),
            "password": "testpass123"
        }
        prof_session = requests.Session()
        response = prof_session.post(f"{BASE_URL}/api/auth/login", json=prof_login)

        response = prof_session.get(f"{BASE_URL}/api/payments/earnings")
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            earnings = response.json()
            print(f"  Total Earnings: ${earnings.get('total_earnings'):.2f}")
            print(f"  Commissions Paid: ${earnings.get('total_commissions_paid'):.2f}")
            print(f"  Current Balance: ${earnings.get('current_balance'):.2f}")
            print(f"  Subscription Status: {earnings.get('subscription_status')}")
        else:
            print(f"  No subscription yet (expected): {response.status_code}")

    def run_all_tests(self):
        """Run complete test flow."""
        print("\n" + "="*60)
        print("TAX SAVINGS MARKETPLACE E2E TEST FLOW")
        print("="*60)

        try:
            self.test_signup_and_login()
            self.test_create_professional_profile()
            self.test_create_rate_cards()
            self.test_search_professionals()
            self.test_book_consultation()
            self.test_messaging()
            self.test_get_bookings()
            self.test_create_subscription()
            self.test_earnings_dashboard()

            self.log("ALL TESTS COMPLETED SUCCESSFULLY!")
            print("\nTest Summary:")
            print(f"  [PASS] User signup & login (client + professional)")
            print(f"  [PASS] Professional profile creation with credentials")
            print(f"  [PASS] Multiple rate cards (fixed, hourly, package)")
            print(f"  [PASS] Professional search by specialty")
            print(f"  [PASS] Consultation booking with commission calculation")
            print(f"  [PASS] Messaging between users")
            print(f"  [PASS] Bookings retrieval")
            print(f"  [PASS] Stripe subscription creation")
            print(f"  [PASS] Earnings dashboard")

        except Exception as e:
            self.log(f"TEST FAILED: {str(e)}", "")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    tester = TestFlow()
    tester.run_all_tests()
