const fs = require("fs");

const DESIGN_ID = "DAHWYLOY8G0";
const CLIENT_ID = process.env.CANVA_CLIENT_ID;
const CLIENT_SECRET = process.env.CANVA_CLIENT_SECRET;
const REFRESH_TOKEN = process.env.CANVA_REFRESH_TOKEN;
const BASE = "https://api.canva.com/rest/v1";

for (const [name, value] of Object.entries({
  CANVA_CLIENT_ID: CLIENT_ID,
  CANVA_CLIENT_SECRET: CLIENT_SECRET,
  CANVA_REFRESH_TOKEN: REFRESH_TOKEN
})) {
  if (!value) {
    console.error(name + " is missing.");
    process.exit(1);
  }
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function getAccessToken() {
  const credentials = Buffer.from(CLIENT_ID + ":" + CLIENT_SECRET).toString("base64");
  const response = await fetch(BASE + "/oauth/token", {
    method: "POST",
    headers: {
      Authorization: "Basic " + credentials,
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: REFRESH_TOKEN
    })
  });

  const text = await response.text();
  if (!response.ok) throw new Error("Token refresh failed: " + response.status + " - " + text);

  const data = JSON.parse(text);
  if (!data.access_token) throw new Error("No access token returned from Canva.");

  console.log("Canva access token obtained successfully.");
  console.log("Granted scope:", data.scope || "(not returned)");
  return data.access_token;
}

async function apiRequest(token, path, options = {}) {
  return fetch(BASE + path, {
    ...options,
    headers: {
      Authorization: "Bearer " + token,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });
}

async function main() {
  fs.mkdirSync("downloads", { recursive: true });
  const token = await getAccessToken();

  console.log("Creating Canva JPG export:", DESIGN_ID);

  const create = await apiRequest(token, "/exports", {
    method: "POST",
    body: JSON.stringify({
      design_id: DESIGN_ID,
      format: { type: "jpg" }
    })
  });

  const createText = await create.text();
  if (!create.ok) throw new Error("Create export failed: " + create.status + " - " + createText);

  const createData = JSON.parse(createText);
  const exportId = createData.job?.id;
  if (!exportId) throw new Error("No export job ID returned.");

  console.log("Export job:", exportId);
  console.log("Status:", createData.job?.status);

  let job = createData.job;

  for (let i = 1; i <= 12 && job.status === "in_progress"; i++) {
    await sleep(5000);

    const poll = await apiRequest(token, "/exports/" + encodeURIComponent(exportId));
    const pollText = await poll.text();

    if (!poll.ok) throw new Error("Poll failed: " + poll.status + " - " + pollText);

    job = JSON.parse(pollText).job || {};
    console.log("Poll", i, "status:", job.status);

    if (job.status === "failed") {
      throw new Error("Canva export failed: " + JSON.stringify(job.error));
    }
  }

  if (job.status !== "success") {
    throw new Error("Export did not complete. Final status: " + job.status);
  }

  const url = job.urls?.[0];
  if (!url) throw new Error("Export succeeded but no download URL was returned.");

  const image = await fetch(url);
  if (!image.ok) throw new Error("CDN download failed: " + image.status);

  const bytes = Buffer.from(await image.arrayBuffer());
  if (bytes.length < 10000) throw new Error("Downloaded file is unexpectedly small.");

  fs.writeFileSync("downloads/official-thumbnail.jpg", bytes);
  console.log("SUCCESS:", bytes.length, "bytes");
}

main().catch(err => {
  console.error("TEST FAILED:", err.message);
  process.exit(1);
});
