# Troubleshooting Google Sheets API Authentication

## Error: "Access blocked: App has not completed the Google verification process"

### Problem
You see this error when trying to authenticate:
```
Access blocked: NCSAA has not completed the Google verification process
Error 403: access_denied
```

### Root Cause
Your OAuth consent screen is in **Testing** mode, which means:
- Only approved test users can access the app
- Your email (`madridmaestro01@gmail.com`) is not in the test users list
- Google requires apps to be verified before allowing public access

### Solution: Add Test Users

Follow these steps to add yourself as a test user:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Select your project

2. **Navigate to OAuth Consent Screen**
   - Go to **APIs & Services** → **OAuth consent screen**

3. **Add Test Users**
   - Scroll down to the **Test users** section
   - Click **+ ADD USERS**
   - Enter your email: `madridmaestro01@gmail.com`
   - Click **ADD**
   - Save the changes

4. **Try Authentication Again**
   ```bash
   python scripts/google_auth.py
   ```

### Alternative: Publish Your App (For Production)

If you want to allow any Google account to use your app:

1. **Complete OAuth Consent Screen**
   - Fill in all required fields
   - Add privacy policy URL (required for production)
   - Add terms of service URL (required for production)

2. **Submit for Verification**
   - Click **PUBLISH APP** button
   - Google will review your app (can take days/weeks)
   - Once verified, any user can access it

**Note:** For development/testing, it's easier to just add test users.

### Quick Fix Steps Summary

```
1. Google Cloud Console → Your Project
2. APIs & Services → OAuth consent screen
3. Scroll to "Test users" section
4. Click "+ ADD USERS"
5. Add: madridmaestro01@gmail.com
6. Save
7. Run: python scripts/google_auth.py again
```

### Other Common Issues

#### Issue: "Invalid client" or "Invalid credentials"
- **Solution:** Make sure `credentials.json` is in the project root
- Verify Client ID and Secret are correct

#### Issue: "Redirect URI mismatch"
- **Solution:** In Google Cloud Console, check that redirect URIs include:
  - `http://localhost`
  - `http://localhost:8080/` (if using that port)

#### Issue: "Token expired"
- **Solution:** The service auto-refreshes tokens, but if it fails:
  - Delete `token.json`
  - Run `python scripts/google_auth.py` again

### Still Having Issues?

1. Check that Google Sheets API is enabled
2. Verify OAuth consent screen is configured
3. Ensure test users are added
4. Check that credentials.json format is correct
5. Make sure you're using the correct project

