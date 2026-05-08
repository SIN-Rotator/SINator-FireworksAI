#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════════════
  FIREWORKS API STATUS CHECK
═══════════════════════════════════════════════════════════════════════════════════════

  ZWECK: Prüfe ob der Fireworks Account für alpha-panther-870@gmx.de
         über die REST API erreichbar / verifiziert ist.
         
  WARUM: Wenn der Account bereits existiert und verifiziert ist,
         brauchen wir keine Verify-Email und können direkt zum
         API-Key erstellen springen.
═══════════════════════════════════════════════════════════════════════════════════════
"""
import asyncio
import httpx

async def check_fireworks_api():
    email = "alpha-panther-870@gmx.de"
    password = "SinatorTest2024!"
    
    # Fireworks hat eine GraphQL/REST API. Wir probieren den Login-Endpoint.
    # Der Login-Endpoint ist typischerweise POST https://app.fireworks.ai/api/auth/callback/credentials
    # oder POST https://app.fireworks.ai/api/v1/auth/login
    
    print(f"Prüfe Fireworks Login für: {email}")
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # Versuche 1: Fireworks Credentials Callback (NextAuth Pattern)
        login_url = "https://app.fireworks.ai/api/auth/callback/credentials"
        try:
            resp = await client.post(login_url, data={
                "email": email,
                "password": password,
                "callbackUrl": "https://app.fireworks.ai/dashboard",
                "csrfToken": "",  # brauchen wir evtl. einen echten CSRF Token
                "json": "true",
            }, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            })
            print(f"\n[NextAuth Callback] Status: {resp.status_code}")
            print(f"[NextAuth Callback] URL: {resp.url}")
            print(f"[NextAuth Callback] Body (first 500): {resp.text[:500]}")
        except Exception as e:
            print(f"[NextAuth Callback] Error: {e}")
        
        # Versuche 2: Fireworks REST API Login (falls existent)
        rest_login_url = "https://api.fireworks.ai/v1/auth/login"
        try:
            resp2 = await client.post(rest_login_url, json={
                "email": email,
                "password": password,
            }, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            })
            print(f"\n[REST API Login] Status: {resp2.status_code}")
            print(f"[REST API Login] Body (first 500): {resp2.text[:500]}")
        except Exception as e:
            print(f"[REST API Login] Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_fireworks_api())
