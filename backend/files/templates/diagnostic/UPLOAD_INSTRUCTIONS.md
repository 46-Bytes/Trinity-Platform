# Template Upload Instructions

## Method 1: API Upload (Recommended for Development)

Use the admin API endpoint to upload templates:

**Endpoint:** `POST /api/diagnostics/templates/upload`

**Requirements:**
- Admin, Firm Admin, or Super Admin role
- File must be .docx format

**Example using curl:**
```bash
curl -X POST "http://your-server/api/diagnostics/templates/upload" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -F "file=@/path/to/your-template.docx"
```

**Example using JavaScript/Fetch:**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('/api/diagnostics/templates/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${authToken}`
  },
  body: formData
});
```

## Method 2: Manual Upload (For Production Servers)

### Via SSH/SCP:

1. **Connect to your server:**
   ```bash
   ssh user@your-server.com
   ```

2. **Navigate to the templates directory:**
   ```bash
   cd /path/to/backend/files/templates/diagnostic
   ```

3. **Upload files using SCP (from your local machine):**
   ```bash
   scp /path/to/local/template.docx user@your-server.com:/path/to/backend/files/templates/diagnostic/
   ```

### Via FTP/SFTP:

1. Connect to your server using an FTP client (FileZilla, WinSCP, etc.)
2. Navigate to: `backend/files/templates/diagnostic/`
3. Upload your .docx template files

### Via Docker/Container:

If your application runs in a container:

1. **Copy files into container:**
   ```bash
   docker cp /path/to/template.docx container-name:/app/backend/files/templates/diagnostic/
   ```

2. **Or mount a volume:**
   Add to your docker-compose.yml:
   ```yaml
   volumes:
     - ./templates:/app/backend/files/templates/diagnostic
   ```

## Method 3: Git Repository (For Version Control)

1. Add template files to your repository:
   ```bash
   git add backend/files/templates/diagnostic/*.docx
   git commit -m "Add document templates"
   git push
   ```

2. On server, pull the changes:
   ```bash
   git pull
   ```

## File Requirements

- **Format:** .docx (Word Document)
- **Placeholders:** Use `{{field_name}}` syntax
- **Naming:** Use descriptive names (spaces, hyphens, underscores are allowed)

## After Upload

1. **Restart the server** (if needed) to ensure templates are detected
2. Templates will automatically appear in the dropdown when generating documents
3. Check logs if templates don't appear:
   ```bash
   # Check backend logs for template loading messages
   ```

## Troubleshooting

### Templates not appearing?

1. **Check file location:** Files must be in `backend/files/templates/diagnostic/`
2. **Check file extension:** Must be `.docx` (not `.doc`)
3. **Check permissions:** Server must have read access to the directory
4. **Restart server:** Sometimes a restart is needed to detect new files
5. **Check logs:** Look for errors in server logs

### Permission Errors?

Ensure the server process has write permissions:
```bash
chmod -R 755 backend/files/templates/diagnostic/
chown -R server-user:server-group backend/files/templates/diagnostic/
```

## Delete Templates

**Via API:**
```bash
DELETE /api/diagnostics/templates/{template_name}
```

**Via File System:**
```bash
rm backend/files/templates/diagnostic/template-name.docx
```

