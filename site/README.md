# Assistant Manager Site

This example shows a minimal offline-capable website for creating, viewing, editing and deleting "assistants". It now includes user registration, authentication and a profile page for changing passwords. The dashboard page offers a search box to filter assistants and Bootstrap provides the styling. Informational messages appear after actions like login or creation. The server uses Python's built-in `http.server` module so no external dependencies are required.

## Running

```
python3 site/server.py
```

The server listens on port 8000. After starting it, open `http://localhost:8000` in your browser. Register an account, log in and use the dashboard to manage assistants. Visit the profile page to change your password.
