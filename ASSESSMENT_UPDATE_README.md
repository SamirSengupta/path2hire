
Changes made (automated patch by assistant):
1. Assessment UI updated to show ONE question at a time. New per-question flow implemented.
   - New routes: /assessment -> starts attempt and redirects to /assessment/0
                 /assessment/<idx> -> shows question idx
                 /answer (POST) -> saves answer and redirects to next or submit
2. Templates: templates/assessment.html updated to match site look and use Tailwind/header/footer from site/assessment.html.
3. Production-ready changes:
   - app.secret_key changed to 'unicorn-secret-please-change' (please replace with secure random value)
   - DEBUG disabled (app.config['DEBUG'] = False) and app.run debug flag set to False.
   - session cookie settings tightened (HTTPOnly, SameSite=Lax, non-permanent).
   - Added Procfile to run under gunicorn.
4. Session behavior:
   - Visiting GET /login clears session to force re-authentication (addresses the 'back and login again' case).
   - Attempt timeouts clear session and force login (30 minute timeout remains).
5. submit() updated to accept answers saved per-question (legacy form submission still supported).
6. A README has been added here explaining the changes.

Notes / Next steps for production:
- Replace app.secret_key with a secure random value (do NOT keep the current secret in public repos).
- Configure HTTPS, reverse proxy, environment variables, and secure storage as appropriate.
- Run with gunicorn (Procfile provided) or similar.
- Test end-to-end on staging before deploying to production.
