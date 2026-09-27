const fs = require("fs");

const DESIGN_ID = "DAHWYLOY8G0";
const TOKEN = process.env.CANVA_API_TOKEN;
const BASE = "https://api.canva.com/rest/v1";

if (!TOKEN) {
  console.error("CANVA_API_TOKEN is missing.");
  process.exit(1);
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function request(path, options = {}) {
  return fetch(BASE + path, {
    ...options,
    headers: {
      Authorization: "Bearer " + TOKEN,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });
}

async function main() {
  fs.mkdirSync("downloads", { recursive: true });

  console.log("Creating Canva JPG export:", DESIGN_ID);

  const create = await request("/exports", {
    method: "POST",
    body: JSON.stringify({
      design_id: DESIGN_ID,
      format: { type: "jpg", quality: 90 }
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

    const poll = await request("/exports/" + encodeURIComponent(exportId));
    const pollText = await poll.text();

    if (!poll.ok) {
      console.log("Poll", i, "HTTP", poll.status);
      continue;
    }

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
