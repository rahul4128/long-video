#!/usr/bin/env node

/**
 * One-time Canva OAuth helper.
 *
 * Run locally on the Ubuntu machine that will be used to administer GitHub:
 *   node scripts/canva_oauth.js
 *
 * The client secret is entered locally and is never written to the repository.
 * The script uses Canva's PKCE Authorization Code flow and listens on:
 *   http://127.0.0.1:3001/oauth/redirect
 *
 * After authorization, it exchanges the code for an access token + refresh
 * token and prints the refresh token. Add that refresh token to GitHub Actions
 * Secrets as CANVA_REFRESH_TOKEN.
 */

const crypto = require("crypto");
const http = require("http");
const { URL } = require("url");
const readline = require("readline");

const REDIRECT_URI = "http://127.0.0.1:3001/oauth/redirect";
const AUTH_URL = "https://www.canva.com/api/oauth/authorize";
const TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token";

const SCOPES = [
  "asset:read",
  "asset:write",
  "design:content:read",
  "design:content:write",
  "design:meta:read",
  "brandtemplate:meta:read",
  "brandtemplate:content:read",
  "profile:read",
].join(" ");

function randomBase64Url(bytes = 96) {
  return crypto.randomBytes(bytes).toString("base64url");
}

function question(rl, prompt, hidden = false) {
  return new Promise((resolve) => {
    if (!hidden) {
      rl.question(prompt, resolve);
      return;
    }

    // Disable terminal echo for the secret.
    const stdin = process.stdin;
    const wasRaw = stdin.isRaw;
    process.stdout.write(prompt);
    stdin.setRawMode?.(true);
    let value = "";

    const onData = (chunk) => {
      const ch = chunk.toString();
      if (ch === "\r" || ch === "\n") {
        stdin.setRawMode?.(wasRaw ?? false);
        stdin.removeListener("data", onData);
        process.stdout.write("\n");
        resolve(value);
      } else if (ch === "\u0003") {
        process.exit(130);
      } else if (ch === "\u007f") {
        value = value.slice(0, -1);
      } else {
        value += ch;
      }
    };

    stdin.on("data", onData);
  });
}

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  try {
    const clientId =
      process.env.CANVA_CLIENT_ID ||
      (await question(rl, "Canva Client ID: "));

    const clientSecret =
      process.env.CANVA_CLIENT_SECRET ||
      (await question(rl, "Canva Client Secret: ", true));

    if (!clientId || !clientSecret) {
      throw new Error("Client ID and Client Secret are required.");
    }

    const codeVerifier = randomBase64Url(96);
    const codeChallenge = crypto
      .createHash("sha256")
      .update(codeVerifier)
      .digest("base64url");
    const state = randomBase64Url(48);

    const auth = new URL(AUTH_URL);
    auth.searchParams.set("code_challenge", codeChallenge);
    auth.searchParams.set("code_challenge_method", "s256");
    auth.searchParams.set("scope", SCOPES);
    auth.searchParams.set("response_type", "code");
    auth.searchParams.set("client_id", clientId);
    auth.searchParams.set("state", state);
    auth.searchParams.set("redirect_uri", REDIRECT_URI);

    const server = http.createServer(async (req, res) => {
      try {
        const requestUrl = new URL(req.url, REDIRECT_URI);

        if (requestUrl.pathname !== "/oauth/redirect") {
          res.writeHead(404);
          res.end("Not found");
          return;
        }

        const returnedState = requestUrl.searchParams.get("state");
        const code = requestUrl.searchParams.get("code");
        const error = requestUrl.searchParams.get("error");

        if (error) {
          res.writeHead(400, { "Content-Type": "text/plain" });
          res.end(`Canva authorization failed: ${error}`);
          throw new Error(`Canva authorization failed: ${error}`);
        }

        if (returnedState !== state) {
          res.writeHead(400, { "Content-Type": "text/plain" });
          res.end("State mismatch.");
          throw new Error("OAuth state mismatch.");
        }

        if (!code) {
          res.writeHead(400, { "Content-Type": "text/plain" });
          res.end("Missing authorization code.");
          throw new Error("Missing authorization code.");
        }

        res.writeHead(200, { "Content-Type": "text/html" });
        res.end("<h2>Canva authorization received.</h2><p>You can close this tab.</p>");

        const basic = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

        const tokenResponse = await fetch(TOKEN_URL, {
          method: "POST",
          headers: {
            Authorization: `Basic ${basic}`,
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({
            grant_type: "authorization_code",
            code,
            code_verifier: codeVerifier,
            redirect_uri: REDIRECT_URI,
          }),
        });

        const tokenText = await tokenResponse.text();
        let token;
        try {
          token = JSON.parse(tokenText);
        } catch {
          token = { raw: tokenText };
        }

        if (!tokenResponse.ok) {
          throw new Error(
            `Canva token exchange failed (${tokenResponse.status}): ${JSON.stringify(token)}`
          );
        }

        console.log("\n=== CANVA OAUTH SUCCESS ===");
        console.log("Access token received:", Boolean(token.access_token));
        console.log("Refresh token received:", Boolean(token.refresh_token));
        console.log("\nCANVA_REFRESH_TOKEN=");
        console.log(token.refresh_token);
        console.log("\nAdd the value above to GitHub Actions Secrets as:");
        console.log("  CANVA_REFRESH_TOKEN");
        console.log("\nDo NOT commit the refresh token or send it in chat.");

        setTimeout(() => {
          server.close();
          rl.close();
        }, 250);
      } catch (err) {
        console.error("\nERROR:", err.message);
        setTimeout(() => {
          server.close();
          rl.close();
          process.exitCode = 1;
        }, 250);
      }
    });

    server.listen(3001, "127.0.0.1", () => {
      console.log("\n1) Open this URL in a browser on THIS Ubuntu machine:\n");
      console.log(auth.toString());
      console.log("\n2) Approve the Canva permissions.");
      console.log("3) The browser will return to 127.0.0.1:3001 and this script will print the refresh token.");
      console.log("\nWaiting for Canva callback...\n");

      const { exec } = require("child_process");
      exec(`xdg-open ${JSON.stringify(auth.toString())}`, () => {});
    });

    process.on("SIGINT", () => {
      server.close();
      rl.close();
      process.exit(130);
    });
  } catch (err) {
    rl.close();
    console.error("ERROR:", err.message);
    process.exit(1);
  }
}

main();
