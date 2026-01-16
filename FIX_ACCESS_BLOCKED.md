# Fix: Access Blocked Error - Step by Step

## Current Error
```
Access blocked: NCSAA has not completed the Google verification process
Error 403: access_denied
```

## Complete Fix Checklist

### ✅ Step 1: Verify OAuth Consent Screen Status

1. Go to: https://console.cloud.google.com/apis/credentials/consent
2. Select your project
3. Check the **Publishing status** at the top
   - If it says **"Testing"** → Continue to Step 2
   - If it says **"In production"** → Skip to Step 4

### ✅ Step 2: Add Test Users (CRITICAL)

1. On the OAuth consent screen page, scroll down to **"Test users"** section
2. Click **"+ ADD USERS"** button
3. Enter your email: **madridmaestro01@gmail.com**
4. Click **"ADD"**
5. **IMPORTANT:** Click **"SAVE"** at the bottom of the page
6. Wait a few seconds for changes to propagate

### ✅ Step 3: Verify Test User Was Added

1. Check the "Test users" list
2. You should see: `madridmaestro01@gmail.com`
3. If not visible, repeat Step 2

### ✅ Step 4: Check App Name

1. On the OAuth consent screen, check the **App name**
2. It should match what you see in the error (likely "NCSAA")
3. If different, note it down

### ✅ Step 5: Verify Scopes

1. On the OAuth consent screen, check **Scopes** section
2. Make sure you have: `https://www.googleapis.com/auth/spreadsheets`
3. If missing, click **"+ ADD OR REMOVE SCOPES"** and add it

### ✅ Step 6: Clear Browser Cache (Optional but Recommended)

Sometimes Google caches the error. Try:
1. Open an **Incognito/Private** browser window
2. Or clear cookies for `accounts.google.com`
3. Run the auth script again

### ✅ Step 7: Wait a Few Minutes

After adding test users, Google may take 1-2 minutes to propagate changes.

## Quick Verification

After completing the steps above, verify:

1. ✅ Test user added: `madridmaestro01@gmail.com`
2. ✅ Status: "Testing" (or "In production")
3. ✅ Scopes include: `https://www.googleapis.com/auth/spreadsheets`
4. ✅ Changes saved

## Still Not Working?

### Alternative: Use a Different Google Account

If you have another Google account that you can add as a test user:
1. Add that account to test users
2. Use that account to authenticate

### Check for Multiple Projects

Make sure you're:
- Using the correct Google Cloud project
- The credentials.json matches the project
- The OAuth consent screen matches the project

## Direct Links

- **OAuth Consent Screen:** https://console.cloud.google.com/apis/credentials/consent
- **Credentials:** https://console.cloud.google.com/apis/credentials
- **APIs:** https://console.cloud.google.com/apis/library

