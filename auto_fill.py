import time
import os
from datetime import datetime
import requests
import pandas as pd
from seleniumbase import Driver
from selenium.webdriver.common.by import By
import re 

# ----------------- CONFIG -----------------
URL = "https://www.eldorado.gg/"
EXCEL_FILE = "data.xlsx"
SCRAPED_FILE = "scraped.xlsx"
CAPTCHA_API_KEY = "c30107ff0d5f8e2a181c5a4593d89cc9"
POLL_INTERVAL = 5
POLL_TIMEOUT = 180

# Behavior: if continue click fails, treat as credential failure and delete row
treat_as_cred_fail_on_continue_click_fail = True

# XPaths
XPATH_EMAIL = '/html/body/main/div/div/div/div/div/div/div/div/div/div[3]/div/div/div[2]/form/div/div[2]/div/div[2]/div/div/div/div/div/input'
XPATH_NEXT_BTN = '//*[@id="primary-form"]/div/div[3]/div/div[1]/button'
XPATH_PASSWORD = '/html/body/main/form/div/div/div/div/div/div/div/div/div/div[3]/div/div[1]/div/div[2]/div/div/div/div/div/input'

# New XPaths for Review Scrape 
XPATH_ACTION_ICON = '//*[@id="topbar"]/nav/div[2]/eld-navbar-action-icon/div/eld-icon/div'
XPATH_VIEW_PROFILE_LINK = '/html/body/eld-root/div[2]/div/div/div/eld-dashboard/div/eld-dashboard-sidenav/div/nav/eld-dashboard-view-profile/a/div/span'
XPATH_REVIEW_DATA = '/html/body/eld-root/div[2]/div/div/div/eld-user-page/section/div/eld-user-panel/div/div[1]/eld-user-profile/div/div[2]/eld-user-profile-feedback/div/div'

# SUSPENDED Status XPaths (for reliable check)
# Check 1: Most reliable text-based check in the dropdown area (Highest Priority)
# dropdown ke andar 'Suspended' text ko dhoondhta hai.
XPATH_SUSPENDED_TEXT_CHECK_DROPDOWN = '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown//*[contains(text(), "Suspended")]'

# Check 2: USER'S PROVIDED SPECIFIC XPATH (Fallback 1)
XPATH_SUSPENDED_BUTTON_USER = '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[1]/div[2]/eld-suspended-button/div/eld-button/button'

# Check 3: Simple component name (Fallback 2)
XPATH_SUSPENDED_BUTTON_SIMPLE = "//eld-suspended-button" 
# Detailed original (Fallback 3 - rarely used)
XPATH_SUSPENDED_BUTTON_DETAILED = '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[1]/div[2]/eld-suspended-button/div/eld-button/button/span/span'


# Continue button selectors
CONTINUE_SELECTORS = [
    ("xpath", '//*[@id="primary-form"]/div/div/div/div/div/div/div/div/div/div[3]/div/div[2]/div/div[1]/button'),
    ("xpath", '/html/body/main/form/div/div/div/div/div/div/div/div/div/div[3]/div/div[2]/div/div[1]/button'),
    ("css", '#primary-form > div > div > div > div > div > div > div > div > div > div:nth-child(3) > div > div:nth-child(2) > div > div:nth-child(1) > button'),
    ("js", 'document.querySelector("#primary-form > div > div > div > div > div > div > div > div > div > div:nth-child(3) > div > div:nth-child(2) > div > div:nth-child(1) > button") && document.querySelector("#primary-form > div > div > div > div > div > div > div > div > div > div:nth-child(3) > div > div:nth-child(2) > div > div:nth-child(1) > button").click()')
]

# Login button selectors (homepage)
LOGIN_BTN_SELECTORS = [
    ("xpath", "//button[contains(text(), 'Login') or contains(text(), 'Sign In')]"),
    ("xpath", '//*[@id="topbar"]/nav/div[2]/eld-navbar-links/div/eld-button/button'),
    ("xpath", '/html/body/eld-root/eld-navbar/header/div[1]/nav/div[2]/eld-navbar-links/div/eld-button/button'),
    ("css", '#topbar > nav > div.activities-area.navbar-content.flex > eld-navbar-links > div > eld-button > button')
]

# Post-login element to click (Profile Icon/Dropdown Trigger)
POST_LOGIN_SELECTORS = [
    ("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[1]/div/div/eld-profile-picture/div/div/eld-image/img'),
    ("xpath", '/html/body/eld-root/eld-navbar/header/div[1]/nav/div[2]/eld-user-dropdown/div[1]/div/div/eld-profile-picture/div/div/eld-image/img'),
    ("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div/div/div/eld-profile-picture/div'),
    ("xpath", '/html/body/eld-root/eld-navbar/header/div[1]/nav/div[2]/eld-user-dropdown/div/div/div/eld-profile-picture/div'),
]

# Logout selectors (Link inside the dropdown)
LOGOUT_SELECTORS = [
    ("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[2]/a/div'),
    ("xpath", '/html/body/eld-root/eld-navbar/header/div[1]/nav/div[2]/eld-user-dropdown/div[2]/div[2]/a/div'),
    ("css", '#topbar > nav > div.activities-area.navbar-content.flex.navbar-content-authenticated > eld-user-dropdown > div.p-\[10px\].top-\[60px\].user-dropdown-list > div.list > a > div')
]
# ------------------------------------------


# ----------------- HELPERS -----------------
def save_debug_state(driver, name_prefix="debug"):
    """Debugging ke liye screenshot aur page source save karta hai."""
    ts = int(time.time())
    png = f"{name_prefix}_{ts}.png"
    html = f"{name_prefix}_{ts}.html"
    try:
        driver.save_screenshot(png)
    except Exception as e:
        print("Screenshot save nahi ho saka:", e)
    try:
        src = driver.get_page_source()
        with open(html, "w", encoding="utf-8") as f:
            f.write(src)
    except Exception as e:
        print("Page source save nahi ho saka:", e)
    print("Debug files save ho gaye:", png, html)


def robust_type(driver, xpath, text, label="input", max_attempts=3):
    """Element mein text type karne ki koshish karta hai, error hone par dobara try karta hai."""
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[{label}] Attempt {attempt} typing '{text}'")
            driver.wait_for_element_visible(xpath, timeout=12)
            el = driver.find_element("xpath", xpath)
            driver.type(xpath, text, timeout=5)
            time.sleep(1)
            val = driver.execute_script("return arguments[0].value;", el)
            if val and str(val).strip():
                return True
        except Exception as e:
            print(f"[{label}] Error:", e)
        time.sleep(1)
    save_debug_state(driver, name_prefix=f"{label}_fail")
    return False


def robust_click_any(driver, selectors, label="button", max_attempts=5):
    """Multiple selectors ka use karke element ko click karne ki koshish karta hai."""
    for attempt in range(1, max_attempts + 1):
        print(f"[{label}] Attempt {attempt} click (Max {max_attempts} attempts)")
        for sel_type, sel_value in selectors:
            try:
                if sel_type == "xpath":
                    driver.wait_for_element_visible(sel_value, timeout=6)
                    driver.click(sel_value)
                    time.sleep(1.5) # Increased sleep after click for stability
                    print(f"[{label}] Clicked via XPATH: {sel_value}")
                    return True
                elif sel_type == "css":
                    driver.wait_for_element_visible(sel_value, by="css selector", timeout=6)
                    driver.click(sel_value, by="css selector")
                    time.sleep(1.5) # Increased sleep after click for stability
                    print(f"[{label}] Clicked via CSS: {sel_value}")
                    return True
                elif sel_type == "js":
                    # For JS, we just execute and assume it works if no exception
                    driver.execute_script(sel_value)
                    time.sleep(1.5) # Increased sleep after click for stability
                    print(f"[{label}] Clicked via JS")
                    return True
            except Exception as e:
                # Error ko sirf debug ke liye rakhein, har attempt par print na karein
                pass 
        time.sleep(1)
    # Only save debug state if ALL attempts fail
    print(f"[FAIL] {label} click failed after {max_attempts} attempts.")
    save_debug_state(driver, name_prefix=f"{label}_click_fail")
    return False


def click_login_button(driver):
    """Homepage par Login button click karta hai."""
    print("[STEP] Trying to click homepage Login button...")
    ok = robust_click_any(driver, LOGIN_BTN_SELECTORS, label="login")
    if not ok:
        print("[ERROR] Login button homepage par nahi mila!")
    else:
        print("[OK] Login button click ho gaya")
    return ok


def click_post_login(driver):
    """Login ke baad profile icon click karke dropdown kholta hai."""
    print("[STEP] Trying to click post-login (profile) button to open dropdown...")
    ok = robust_click_any(driver, POST_LOGIN_SELECTORS, label="post-login-profile-icon")
    if not ok:
        print("[INFO] Post-login profile icon nahi mila/click nahi ho saka; aage badh rahe hain.")
    else:
        print("[OK] Post-login profile icon click ho gaya")
    return ok


# ----------------- CAPTCHA HANDLING (No Change) -----------------
def find_recaptcha_sitekey(driver):
    """reCAPTCHA site key search karta hai."""
    try:
        iframe = driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
        src = iframe.get_attribute("src")
        match = re.search(r"sitekey=([^&]+)", src)
        if match:
            return match.group(1)
    except Exception:
        pass
    
    try:
        sitekey_divs = driver.find_elements(By.XPATH, "//div[@data-sitekey]")
        if sitekey_divs:
            return sitekey_divs[0].get_attribute("data-sitekey")
    except Exception:
        pass

    return None

def request_2captcha_token(api_key, sitekey, pageurl):
    """Captcha 2Captcha ko bhejkar solution token leta hai."""
    print("[CAPTCHA] Token request ho raha hai...")
    submit_url = f"https://2captcha.com/in.php?key={api_key}&method=userrecaptcha&googlekey={sitekey}&pageurl={pageurl}"
    
    try:
        resp = requests.get(submit_url)
        if "OK|" not in resp.text:
            print(f"[ERROR] 2Captcha submission fail ho gaya: {resp.text}")
            return None
        captcha_id = resp.text.split("|")[1]
    except Exception as e:
        print(f"[ERROR] 2Captcha submission se communication fail ho gaya: {e}")
        return None

    print(f"[CAPTCHA] Captcha ID: {captcha_id}. Solution ka intezaar (max {POLL_TIMEOUT}s)...")
    start_time = time.time()
    result_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}"

    while time.time() - start_time < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            resp = requests.get(result_url)
            if "CAPCHA_NOT_READY" in resp.text:
                print("[CAPTCHA] Ready nahi hai, intezaar...")
                continue
            
            if "OK|" in resp.text:
                token = resp.text.split("|")[1]
                print("[CAPTCHA] Solution mil gaya.")
                return token
            
            print(f"[ERROR] 2Captcha retrieval fail ho gaya: {resp.text}")
            return None
        except Exception as e:
            print(f"[ERROR] 2Captcha retrieval se communication fail ho gaya: {e}")
            return None

    print("[ERROR] 2Captcha solution timeout ho gaya.")
    return None

def inject_recaptcha_token(driver, token):
    """Solve kiya hua reCAPTCHA token page mein inject karta hai."""
    try:
        script = f'document.getElementById("g-recaptcha-response").innerHTML = "{token}";'
        driver.execute_script(script)
        print("[CAPTCHA] Token JS ke zariye inject ho gaya.")
        time.sleep(1) 
        return True
    except Exception as e:
        print(f"[ERROR] Token inject nahi ho saka: {e}")
        return False
        
# ----------------- LOGOUT/ACCOUNT STATUS -----------------

def is_account_blocked(driver):
    """Check karta hai ki account suspended/blocked hai ya nahi (full page error)."""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        keywords = ["suspended", "locked", "disabled", "account is inactive", "access denied", "blocked"]
        if any(k in body_text.lower() for k in keywords):
            print(f"[DETECT] Account blocked/suspended page mila (text search).")
            return True
        
        if driver.is_element_visible("//h1[contains(text(), 'Access Denied')]", by=By.XPATH, timeout=1):
            print("[DETECT] Access Denied H1 mila.")
            return True
        if driver.is_element_visible("eld-error-message", by=By.TAG_NAME, timeout=1):
            print("[DETECT] Generic error message element mila.")
            return True
            
    except Exception as e:
        print(f"[WARN] Blocked status check mein error: {e}")
    return False


def try_logout(driver):
    """Logout karne ki koshish karta hai."""
    print("[STEP] Logout karne ki koshish (ENHANCED)...")
    
    logout_clicked = robust_click_any(driver, LOGOUT_SELECTORS, label="logout_direct", max_attempts=5)
    
    if logout_clicked:
        print("[OK] Logout successful (direct click).")
        return True

    print("[INFO] Logout button visible nahi hai. Profile icon click karke menu khol rahe hain...")
    profile_clicked = click_post_login(driver) 
    
    if not profile_clicked:
        print("[WARN] Profile icon click nahi ho saka. Logout ki guarantee nahi.")
        return False
        
    time.sleep(1.5) 

    logout_clicked_after_menu = robust_click_any(driver, LOGOUT_SELECTORS, label="logout_after_menu", max_attempts=5)
    
    if logout_clicked_after_menu:
        print("[OK] Logout successful (menu kholne ke baad).")
        return True
    else:
        print("[ERROR] Final logout click fail ho gaya. Next loop fresh start karega.")
        return False


# ----------------- SCRAPING FUNCTIONS -----------------

def scrape_profile_data(driver, email, password):
    """Initial profile data aur Suspension Status scrape karta hai (ENHANCED)."""
    print("[STEP] Initial profile data scrape ho raha hai...")
    
    # --- 1. Verification Required (Tassdeeq ki Zarurat) check ---
    try:
        verification_alert = driver.find_element(
            By.XPATH, 
            '//div[contains(text(), "Verification required") or contains(text(), "2FA")]'
        )
        if verification_alert.is_displayed():
            print(f"[SKIP] Account {email} ko verification/2FA ki zaroorat hai. Logging aur skip kar rahe hain.")
            append_scraped_profile(email, password, "N/A", "N/A", "N/A", "N/A", "N/A", status="SKIPPED - Verification Required")
            return None, None, None, "N/A" 
    except Exception:
        pass 

    # --- 2. Open dropdown for scraping and suspension check ---
    # Profile icon ko click karein taake dropdown open ho jaye (MUST)
    click_post_login(driver)
    
    # Wait time badhaya gaya hai (4 seconds) taake dropdown ke elements load ho sakein.
    time.sleep(4.0) 

    # --- 3. Suspended Status Check (Enhanced Robust Logic) ---
    is_suspended = "No"
    
    # Check 1: Highest Priority: Text search within the specific dropdown component.
    try:
        # Check if the element containing 'Suspended' text inside the dropdown is visible
        if driver.is_element_visible("xpath", XPATH_SUSPENDED_TEXT_CHECK_DROPDOWN, timeout=3):
            is_suspended = "Yes"
            print("[STATUS] Account **SUSPENDED** hai (Highest Priority Text Search successful).")
        # Check 2: User's Provided Specific XPATH (Fallback 1)
        elif driver.is_element_visible("xpath", XPATH_SUSPENDED_BUTTON_USER, timeout=1):
            is_suspended = "Yes"
            print("[STATUS] Account **SUSPENDED** hai (User's Specific XPath successful - Fallback 1).")
        # Check 3: Simple component-based XPath (Fallback 2)
        elif driver.is_element_visible("xpath", XPATH_SUSPENDED_BUTTON_SIMPLE, timeout=1):
            is_suspended = "Yes"
            print("[STATUS] Account **SUSPENDED** hai (Simple component check successful - Fallback 2).")
        # Check 4: Detailed original (Fallback 3)
        elif driver.is_element_visible("xpath", XPATH_SUSPENDED_BUTTON_DETAILED, timeout=1):
            is_suspended = "Yes"
            print("[STATUS] Account **SUSPENDED** hai (Detailed XPath check successful - Fallback 3).")
        else:
            is_suspended = "No"
            print("[STATUS] Account suspended nahi hai ('No').")
    except Exception as e:
        # Agar error aaye (yaani element mil hi nahi saka), toh 'No' hi manein
        print(f"[WARN] Suspension check mein error: {e}. 'No' maan kar aage badh rahe hain.")
        is_suspended = "No"


    # --- 4. Standard Dropdown Scraping ---
    name, price, rank = "Not Found", "Not Found", "Not Found"

    try:
        # Yeh XPaths dropdown khule hone ki soorat mein kaam karte hain
        name = driver.find_element("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[1]/div[1]/div[1]/div/a/h5').text.strip()
    except Exception:
        pass

    try:
        price = driver.find_element("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[1]/div[1]/div[1]/div/div/span').text.strip()
    except Exception:
        pass

    try:
        rank = driver.find_element("xpath", '//*[@id="topbar"]/nav/div[2]/eld-user-dropdown/div[2]/div[1]/div[1]/div[1]/div/div/eld-loyalty-rank/div/a').text.strip()
    except Exception:
        pass

    print(f"[OK] Scraped Initial Data: {name} | {price} | {rank} | Suspended: {is_suspended}")
    
    # Is_suspended status ko bhi return karein
    return name, price, rank, is_suspended


def scrape_review_data(driver):
    """Review data scrape karne ke liye doosre clicks karta hai."""
    print("[STEP] Review Data Scrape shuru ho raha hai...")
    review_data = "Not Found"
    
    # 1. Click the action icon (first click)
    action_icon_selectors = [("xpath", XPATH_ACTION_ICON)]
    if not robust_click_any(driver, action_icon_selectors, label="action_icon"):
        print("[WARN] Action icon click nahi ho saka. Review scrape skip kar rahe hain.")
        return review_data

    # 2. Click the view profile link (second click - navigation)
    view_profile_selectors = [("xpath", XPATH_VIEW_PROFILE_LINK)]
    if not robust_click_any(driver, view_profile_selectors, label="view_profile_link"):
        print("[WARN] View profile link click nahi ho saka. Review scrape ka baaki hissa skip kar rahe hain.")
        return review_data

    time.sleep(3) # Wait for profile page to load

    # 3. Scrape the review data
    try:
        review_element = driver.find_element("xpath", XPATH_REVIEW_DATA)
        review_data = review_element.text.strip()
        print(f"[OK] Review Data Scrape ho gaya: {review_data}")
    except Exception as e:
        print(f"[WARN] Review data scrape nahi ho saka ({XPATH_REVIEW_DATA}). Error: {e}")
        save_debug_state(driver, name_prefix="review_scrape_fail")

    return review_data


def append_scraped_profile(email, password, name, price, rank, is_suspended, review, status="SUCCESS"):
    """Scrape kiye गए data ko Excel file mein append karta hai."""
    now = datetime.utcnow().isoformat()
    
    if status == "SUCCESS" and name == "Not Found":
        status = "WARN - Login OK, but Scrape Fail"

    row = {
        "Email": email,
        "Password": password,
        "Name": name,
        "Price": price,
        "Rank": rank,
        "Is Suspended": is_suspended,  # Naya column
        "Review": review,              # Review column
        "Timestamp": now,
        "Status": status,
    }
    df_new = pd.DataFrame([row])
    if os.path.exists(SCRAPED_FILE):
        try:
            df_exist = pd.read_excel(SCRAPED_FILE)
            df_out = pd.concat([df_exist, df_new], ignore_index=True)
        except Exception:
            df_out = df_new
    else:
        df_out = df_new
    df_out.to_excel(SCRAPED_FILE, index=False)
    print(f"[OK] 1 row {SCRAPED_FILE} mein append ho gaya (Status: {status})")


# ----------------- LOGIN FAILURE DETECTION (No Change) -----------------
def is_login_failed(driver):
    """Login fail hone ko detect karta hai."""
    try:
        body = driver.find_element("xpath", "//body").text.lower()
    except Exception:
        body = ""

    keywords = [
        "incorrect", "invalid", "wrong", "authentication failed",
        "email or password", "credentials", "unable to log", "login failed",
        "not found", "does not match"
    ]
    for k in keywords:
        if k in body:
            print(f"[DETECT] Page mein error keyword mila: '{k}'")
            return True

    try:
        if driver.is_element_visible(XPATH_EMAIL):
            print("[DETECT] Email input dobara visible hai → Shayad login fail ho gaya")
            return True
    except Exception:
        pass

    return False


def remove_first_row_from_input():
    """Input data.xlsx se pehli row hatha deta hai."""
    if not os.path.exists(EXCEL_FILE):
        return
    try:
        df2 = pd.read_excel(EXCEL_FILE)
        if df2.empty:
            return
        df2 = df2.drop(df2.index[0]).reset_index(drop=True)
        df2.to_excel(EXCEL_FILE, index=False)
        print("[OK] Input file se pehli row hata di gayi (processing/bad credentials/stuck page ki wajah se).")
    except Exception as e:
        print("[WARN] Input file se row nahi hatayi ja saki:", e)


# ----------------- MAIN -----------------
def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"[ERROR] Input file {EXCEL_FILE} nahi mila. Exit kar rahe hain.")
        return

    df = pd.read_excel(EXCEL_FILE)
    if df.empty:
        print("[INFO] Input file khali hai. Kuch nahi karna.")
        return

    driver = Driver(uc=True)
    try:
        while True:
            try:
                df = pd.read_excel(EXCEL_FILE)
            except Exception as e:
                print("[ERROR] Input file read nahi ho saka:", e)
                break

            if df.empty:
                print("[FINISHED] Input file mein aur accounts nahi hain.")
                break

            email = str(df.at[0, "email"]).strip() if "email" in df.columns else ""
            password = str(df.at[0, "password"]).strip() if "password" in df.columns else ""
            print("\n" + "=" * 40)
            print(f"▶ Nayi row shuru ho rahi hai: {email}")
            print("=" * 40)

            # --- Browser Settings ---
            driver.open(URL) 
            time.sleep(3)
            
            # --- START: LOGIN BUTTON CLICK ---
            click_success = click_login_button(driver)
            time.sleep(2)
            
            if not click_success:
                print("[FATAL SKIP] Homepage par Login button click fail ho gaya. Row hata kar agla account try kar rahe hain.")
                append_scraped_profile(email, password, "N/A", "N/A", "N/A", "N/A", "N/A", status="FAIL - Initial Click")
                remove_first_row_from_input()
                continue
            # --- END: LOGIN BUTTON CLICK ---

            # Captcha check (sirf start mein)
            print("[STEP] Captcha check ho raha hai...")
            sitekey = find_recaptcha_sitekey(driver)
            if sitekey:
                print("[INFO] Captcha sitekey mila, 2captcha token request ho raha hai...")
                token = request_2captcha_token(CAPTCHA_API_KEY, sitekey, driver.get_current_url())
                if token:
                    inject_recaptcha_token(driver, token)
                    print("[OK] Captcha inject ho gaya")
                else:
                    print("[WARN] 2captcha ne token nahi diya; agar prompt hua toh manually solve karein")

            # Email
            print("[STEP] Email type ho raha hai...")
            if not robust_type(driver, XPATH_EMAIL, email, label="email"):
                print("[ERROR] Email type fail ho gaya; skip kar rahe hain.")
                continue 

            print("[STEP] NEXT button click ho raha hai...")
            robust_click_any(driver, [("xpath", XPATH_NEXT_BTN)], label="next")
            time.sleep(3)

            # Password
            print("[STEP] Password type ho raha hai...")
            if not robust_type(driver, XPATH_PASSWORD, password, label="password"):
                print("[ERROR] Password typing fail ho gaya; skip kar rahe hain.")
                continue

            print("[STEP] CONTINUE button click ho raha hai...")
            cont_ok = robust_click_any(driver, CONTINUE_SELECTORS, label="continue") 
            time.sleep(4) 

            # --- POST-LOGIN CHECKS ---
            
            # 1. Blocked/Suspended Account Check (Full Page Error)
            if is_account_blocked(driver):
                print(f"[SKIP] Account {email} blocked/suspended page par hai. Logging aur skip kar rahe hain.")
                append_scraped_profile(email, password, "N/A", "N/A", "N/A", "N/A", "N/A", status="SKIPPED - Suspended/Blocked Page")
                remove_first_row_from_input()
                continue
            
            # 2. Check if the 'Continue' click failed 
            if not cont_ok:
                print("[FAIL] 'Continue' click fail ho gaya. Stuck page ya unhandled error maan kar chal rahe hain.")
                append_scraped_profile(email, password, "N/A", "N/A", "N/A", "N/A", "N/A", status="FAIL - Continue Click Stuck/Timeout")
                remove_first_row_from_input()
                continue
                
            # 3. Login Failure Check (Bad Credentials)
            if is_login_failed(driver):
                print("[FAIL] Login fail ho gaya (bad credentials/error page).")
                append_scraped_profile(email, password, "N/A", "N/A", "N/A", "N/A", "N/A", status="FAIL - Bad Credentials")
                remove_first_row_from_input()
                continue

            # Agar yahan tak pohncha, toh login successful aur account theek hai
            
            # User Request: Browser zoom level ko 75% par set karna
            print("[CONFIG] Browser zoom 75% par set ho raha hai...")
            driver.execute_script("document.body.style.zoom='75%';")
            time.sleep(1) 
            
            # Initial Scrape (Name, Price, Rank) aur **Suspension Status** check
            # Yeh function profile icon click karke dropdown kholta hai aur phir status check karta hai
            name, price, rank, is_suspended = scrape_profile_data(driver, email, password)

            # Check for Verification Skip (agar scrape_profile_data se None return hua)
            if name is None:
                print(f"❌ Skipped account (Verification required): {email}")
                remove_first_row_from_input()
                time.sleep(2)
                continue 

            # --- NEW STEP: Review Data Scrape (Suspension check ke baad) ---
            # Ab hum aage ke clicks karke review data scrape karenge
            review = scrape_review_data(driver)
            
            # Profile Icon Click again (dropdown band karne ya agle step ke liye)
            # scrape_profile_data ne dropdown khola tha, isse band karne ki koshish.
            print("[STEP] Profile icon ko dobara click kar rahe hain (agar khula ho toh band ho jaye)...")
            click_post_login(driver) 
            time.sleep(1)

            # Final data append
            append_scraped_profile(email, password, name, price, rank, is_suspended, review, status="SUCCESS")

            # LOGOUT STEP (ENHANCED):
            try_logout(driver)
            time.sleep(2)

            # Remove processed row from input file
            remove_first_row_from_input()

            print(f"✅ Account successfully process ho gaya: {email}")
            time.sleep(2)

        print("\n[FINISHED] Processing complete.")
    finally:
        print("[EXIT] Driver quit ho raha hai.")
        driver.quit()


if __name__ == "__main__":
    main()