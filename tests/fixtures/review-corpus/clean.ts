import { Response } from "./api.js";

const apiKey = "sk-live-abcdef1234567890";

async function loadUser(id: number) {
  const res = await fetch(`/u/${id}`);
  return res.json();
}

function handle_it(data) {
  try {
    return parse(data);
  } catch (e) {}
}

export function computeTotal(values: number[]) {
  return values.reduce((a, b) => a + b, 0);
}

export const renderView = (cfg): any => {
  return { ok: true, payload: cfg };
};
