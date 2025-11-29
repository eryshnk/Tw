import time
import random
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

DATA_FILE = os.environ.get("DATA_FILE", "bot_data.json")

class TwitterBot:
    def __init__(self):
        self.driver = None
        self.is_running = False
        self.is_logged_in = False
        self.follow_history = []
        self.today_follows = 0
        self.total_follows = 0
        self.last_activity = None
        self.current_hashtag = None
        self.load_data()

    def load_data(self):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.follow_history = data.get('follow_history', [])
                    self.total_follows = data.get('total_follows', 0)
                    self.last_activity = data.get('last_activity', None)
                    
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.today_follows = sum(
                        1 for record in self.follow_history 
                        if record.get('timestamp', '').startswith(today)
                    )
        except Exception as e:
            print(f"Veri yukleme hatasi: {e}")

    def save_data(self):
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, 'w') as f:
                json.dump({
                    'follow_history': self.follow_history[-1000:],
                    'total_follows': self.total_follows,
                    'last_activity': self.last_activity
                }, f)
        except Exception as e:
            print(f"Veri kaydetme hatasi: {e}")

    def setup_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            chrome_bin = os.environ.get('CHROME_BIN')
            if chrome_bin:
                chrome_options.binary_location = chrome_bin
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return True
        except Exception as e:
            print(f"Driver kurulum hatasi: {e}")
            return False

    def login(self, username: str, password: str) -> dict:
        try:
            if not self.driver:
                if not self.setup_driver():
                    return {"success": False, "message": "Tarayici baslatilamadi"}

            self.driver.get("https://twitter.com/i/flow/login")
            time.sleep(3)

            try:
                username_input = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
                )
                username_input.clear()
                for char in username:
                    username_input.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                time.sleep(1)
                username_input.send_keys(Keys.RETURN)
            except TimeoutException:
                return {"success": False, "message": "Giris sayfasi yuklenemedi"}

            time.sleep(2)

            try:
                password_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
                )
                password_input.clear()
                for char in password:
                    password_input.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                time.sleep(1)
                password_input.send_keys(Keys.RETURN)
            except TimeoutException:
                try:
                    phone_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]'))
                    )
                    return {"success": False, "message": "Twitter ek dogrulama istiyor. Lutfen manuel giris yapin."}
                except:
                    return {"success": False, "message": "Sifre alani bulunamadi"}

            time.sleep(5)

            if "home" in self.driver.current_url.lower() or self.check_logged_in():
                self.is_logged_in = True
                return {"success": True, "message": "Giris basarili!"}
            else:
                page_source = self.driver.page_source.lower()
                if "wrong password" in page_source or "yanlis sifre" in page_source:
                    return {"success": False, "message": "Yanlis kullanici adi veya sifre"}
                elif "suspended" in page_source or "askiya alindi" in page_source:
                    return {"success": False, "message": "Hesabiniz askiya alinmis"}
                else:
                    return {"success": False, "message": "Giris yapilamadi. Lutfen bilgilerinizi kontrol edin."}

        except Exception as e:
            return {"success": False, "message": f"Giris hatasi: {str(e)}"}

    def check_logged_in(self) -> bool:
        try:
            self.driver.find_element(By.CSS_SELECTOR, '[data-testid="primaryColumn"]')
            return True
        except:
            return False

    def search_hashtag(self, hashtag: str) -> bool:
        try:
            clean_hashtag = hashtag.replace('#', '')
            search_url = f"https://twitter.com/search?q=%23{clean_hashtag}&src=typed_query&f=live"
            self.driver.get(search_url)
            time.sleep(3)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweet"]'))
            )
            self.current_hashtag = clean_hashtag
            return True
        except TimeoutException:
            print(f"Hashtag aramasinda tweet bulunamadi: #{clean_hashtag}")
            return False
        except Exception as e:
            print(f"Hashtag arama hatasi: {e}")
            return False

    def get_users_from_tweets(self) -> list:
        users = []
        try:
            tweets = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
            
            for tweet in tweets[:20]:
                try:
                    user_link = tweet.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"] a')
                    username = user_link.get_attribute('href').split('/')[-1]
                    if username and username not in users:
                        users.append(username)
                except:
                    continue
                    
        except Exception as e:
            print(f"Kullanici bulma hatasi: {e}")
        
        return users

    def follow_user(self, username: str) -> dict:
        try:
            self.driver.get(f"https://twitter.com/{username}")
            time.sleep(2)

            try:
                follow_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid$="-follow"]'))
                )
                
                button_text = follow_button.text.lower()
                if "following" in button_text or "takip ediliyor" in button_text:
                    return {"success": False, "message": "Zaten takip ediyorsunuz", "already_following": True}
                
                follow_button.click()
                time.sleep(1)
                
                now = datetime.now().isoformat()
                record = {
                    "id": str(int(time.time() * 1000)),
                    "username": username,
                    "hashtag": self.current_hashtag or "unknown",
                    "timestamp": now
                }
                self.follow_history.insert(0, record)
                self.today_follows += 1
                self.total_follows += 1
                self.last_activity = now
                self.save_data()
                
                return {"success": True, "message": f"@{username} takip edildi", "record": record}
                
            except TimeoutException:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, '[data-testid$="-unfollow"]')
                    return {"success": False, "message": "Zaten takip ediyorsunuz", "already_following": True}
                except:
                    return {"success": False, "message": "Takip butonu bulunamadi"}
                    
        except Exception as e:
            return {"success": False, "message": f"Takip hatasi: {str(e)}"}

    def run_bot(self, hashtags: list, settings: dict, credentials: dict) -> None:
        self.is_running = True
        max_follows = settings.get('maxFollowsPerRun', 50)
        min_wait = settings.get('minWait', 10)
        max_wait = settings.get('maxWait', 30)
        
        if not self.is_logged_in:
            login_result = self.login(credentials['username'], credentials['password'])
            if not login_result['success']:
                print(f"Giris hatasi: {login_result['message']}")
                self.is_running = False
                return

        follows_this_run = 0
        
        while self.is_running and follows_this_run < max_follows:
            for hashtag in hashtags:
                if not self.is_running:
                    break
                    
                if not self.search_hashtag(hashtag):
                    continue
                
                users = self.get_users_from_tweets()
                
                for username in users:
                    if not self.is_running or follows_this_run >= max_follows:
                        break
                    
                    result = self.follow_user(username)
                    
                    if result['success']:
                        follows_this_run += 1
                        print(f"Takip edildi: @{username} (#{hashtag}) - {follows_this_run}/{max_follows}")
                        
                        wait_time = random.uniform(min_wait, max_wait)
                        time.sleep(wait_time)
                    elif result.get('already_following'):
                        continue
                    else:
                        time.sleep(5)
            
            if follows_this_run < max_follows and self.is_running:
                time.sleep(60)
        
        self.is_running = False
        print(f"Bot durduruldu. Bu calismada {follows_this_run} kisi takip edildi.")

    def stop_bot(self):
        self.is_running = False

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_logged_in": self.is_logged_in,
            "today_follows": self.today_follows,
            "total_follows": self.total_follows,
            "last_activity": self.last_activity,
            "current_hashtag": self.current_hashtag
        }

    def get_history(self, limit: int = 100) -> list:
        return self.follow_history[:limit]

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        self.is_logged_in = False
        self.is_running = False
