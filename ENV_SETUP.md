# Environment Variables Setup Guide

## Overview

The backend uses environment variables to securely manage sensitive credentials, particularly Google Sheets API credentials. This prevents accidentally committing secrets to version control.

## Quick Start

1. **Copy the example file:**
   ```bash
   cd backend
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials** (see options below)

3. **The `.env` file is automatically gitignored** - it will never be committed

## Credentials Setup Options

### Option 1: JSON String (Recommended - Most Secure)

Paste your entire Google service account JSON as a single-line string in `.env`:

```bash
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account","project_id":"ncsaa-484512","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"sheet-reader@ncsaa-484512.iam.gserviceaccount.com",...}'
```

**Advantages:**
- No file needed on disk
- Works well in containerized deployments (Docker, Kubernetes)
- Easy to set in CI/CD pipelines
- Most secure option

**Note:** Make sure to escape quotes properly or use single quotes around the JSON string.

### Option 2: File Path

Set the path to your credentials JSON file:

```bash
GOOGLE_SHEETS_CREDENTIALS_FILE=/absolute/path/to/credentials.json
```

**Advantages:**
- Easy to manage if you already have the file
- Can be placed anywhere on the filesystem

### Option 3: Default Location (Legacy Support)

If neither environment variable is set, the system will look for:
```
backend/credentials/ncsaa-484512-3f8c48632375.json
```

**Note:** This file is gitignored and should not be committed.

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | No* | Complete service account JSON as string | `'{"type":"service_account",...}'` |
| `GOOGLE_SHEETS_CREDENTIALS_FILE` | No* | Path to credentials JSON file | `/path/to/creds.json` |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | No | Google Sheets spreadsheet ID | `1vLzG_4nlYIlmm6iaVEJLt277PLlhvaWXbeR8Rj1xLTI` |

*At least one credentials method must be configured.

## Priority Order

The system checks credentials in this order:

1. **`GOOGLE_SHEETS_CREDENTIALS_JSON`** (highest priority)
2. **`GOOGLE_SHEETS_CREDENTIALS_FILE`**
3. **Default file location** (fallback)

## Security Best Practices

1. ✅ **Never commit `.env` files** - Already in `.gitignore`
2. ✅ **Never commit credential JSON files** - Already in `.gitignore`
3. ✅ **Use environment variables in production** - Set in your deployment platform
4. ✅ **Rotate credentials regularly** - Update your service account keys periodically
5. ✅ **Use least privilege** - Only grant necessary Google Sheets API permissions

## Troubleshooting

### Error: "Google Sheets credentials not found"

**Solution:** Make sure you've:
- Created a `.env` file in the `backend` directory
- Set either `GOOGLE_SHEETS_CREDENTIALS_JSON` or `GOOGLE_SHEETS_CREDENTIALS_FILE`
- Or placed the credentials file at the default location

### Error: "Invalid JSON in GOOGLE_SHEETS_CREDENTIALS_JSON"

**Solution:** 
- Check that your JSON string is properly formatted
- Ensure quotes are escaped correctly
- Try using single quotes around the entire JSON string: `GOOGLE_SHEETS_CREDENTIALS_JSON='{...}'`

### Error: "File not found" for GOOGLE_SHEETS_CREDENTIALS_FILE

**Solution:**
- Use an absolute path, not a relative path
- Verify the file exists at that location
- Check file permissions

## Production Deployment

For production environments (Docker, Kubernetes, cloud platforms):

1. **Set environment variables** in your platform's configuration
2. **Do not include `.env` files** in your Docker image
3. **Use secrets management** (AWS Secrets Manager, Azure Key Vault, etc.)
4. **Example Docker:**
   ```dockerfile
   ENV GOOGLE_SHEETS_CREDENTIALS_JSON=${GOOGLE_SHEETS_CREDENTIALS_JSON}
   ```

## Migration from File-Based Credentials

If you're currently using the default file location:

1. Copy the contents of your `credentials/ncsaa-484512-3f8c48632375.json` file
2. Create `.env` file: `cp .env.example .env`
3. Add to `.env`: `GOOGLE_SHEETS_CREDENTIALS_JSON='<paste JSON here>'`
4. The credentials file is already in the gitignored `credentials/` folder, so it won't be committed

The system will automatically use the environment variable if set.
