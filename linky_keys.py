from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from dotenv import dotenv_values

MASTER_ENV_KEY = "LINKY_MASTER_MNEMO"
DEFAULT_OWNER_MAX_INDEX = 3
DATA_ROOT = Path(r"D:\data_codex")
TMP_DIR = DATA_ROOT / ".tmp"
NPM_CACHE_DIR = DATA_ROOT / ".cache" / "npm"
PIP_CACHE_DIR = DATA_ROOT / ".cache" / "pip"


def ask_print_secrets_to_terminal() -> bool:
    print("This is not how production keys should be handled. This helper is sandbox-only and educational.")
    print("The output can contain a SLIP-39 seed, Nostr nsec, Cashu seed material, and Evolu owner mnemonics.")
    print("By default, only progress is printed; secret material stays in the export file.")
    print('DO YOU REALLY WANT TO PRINT ALL SECRETS TO THE TERMINAL? Type exactly "yes" in lowercase.')
    try:
        answer = input("For the safer default behavior, just press Enter: ")
    except EOFError:
        return False
    return answer.strip() == "yes"

JS_DERIVER = r'''
import { createAppOwner, mnemonicToOwnerSecret, Mnemonic } from "@evolu/common";
import { hmac } from "@noble/hashes/hmac.js";
import { sha512 } from "@noble/hashes/sha2.js";
import { HDKey } from "@scure/bip32";
import { entropyToMnemonic, mnemonicToSeedSync } from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english.js";
import { Effect } from "effect";
import { getPublicKey, nip19 } from "nostr-tools";
import { parseSlip39Share, recoverMasterSecretFromSlip39Share } from "../../packages/core/src/identity/index.ts";

const BIP85_HMAC_KEY = new TextEncoder().encode("bip-entropy-from-k");

const input = JSON.parse(process.env.LINKY_KEYS_INPUT_JSON ?? "{}");
const slip39 = String(input.slip39 ?? "").trim();
const maxOwnerIndex = Math.max(0, Math.trunc(Number(input.maxOwnerIndex ?? 0)));

const hex = (bytes) => Buffer.from(bytes).toString("hex");
const base64 = (bytes) => Buffer.from(bytes).toString("base64");

const bip85Entropy = (root, path, bytes) => {
  const node = root.derive(path);
  if (!node.privateKey) throw new Error(`BIP-85 derivation failed at ${path}`);
  return hmac(sha512, BIP85_HMAC_KEY, node.privateKey).slice(0, bytes);
};

const appOwnerFromMnemonic = (mnemonic) => {
  const parsed = Mnemonic.fromUnknown(mnemonic);
  if (!parsed.ok) {
    return { ok: false, error: "Invalid Evolu owner mnemonic" };
  }
  const ownerSecret = mnemonicToOwnerSecret(parsed.value);
  const appOwner = createAppOwner(ownerSecret);
  return {
    ok: true,
    ownerId: String(appOwner.id),
  };
};

const ownerFromPath = (root, role, index, path) => {
  const entropy = bip85Entropy(root, path, 16);
  const mnemonic = entropyToMnemonic(entropy, wordlist);
  return {
    role,
    index,
    path,
    entropyHex: hex(entropy),
    mnemonic,
    ...appOwnerFromMnemonic(mnemonic),
  };
};

const share = await Effect.runPromise(parseSlip39Share(slip39));
const masterSecret = await Effect.runPromise(recoverMasterSecretFromSlip39Share(share));
const root = HDKey.fromMasterSeed(masterSecret);

const nostrPath = "m/44'/1237'/0'/0/0";
const nostrNode = root.derive(nostrPath);
if (!nostrNode.privateKey) throw new Error(`Nostr derivation failed at ${nostrPath}`);
const nostrPrivateKey = nostrNode.privateKey;
const nostrPublicKeyHex = getPublicKey(nostrPrivateKey);

const cashuPath = "m/83696968'/39'/0'/24'/0'";
const cashuEntropy = bip85Entropy(root, cashuPath, 32);
const cashuMnemonic = entropyToMnemonic(cashuEntropy, wordlist);
const cashuSeed = mnemonicToSeedSync(cashuMnemonic);

const owners = [];
owners.push(ownerFromPath(root, "meta", 0, "m/83696968'/39'/0'/24'/1'/0'"));
owners.push(ownerFromPath(root, "identity", 0, "m/83696968'/39'/0'/24'/6'/0'"));

for (let index = 0; index <= maxOwnerIndex; index += 1) {
  owners.push(ownerFromPath(root, "contacts", index, `m/83696968'/39'/0'/24'/2'/${index}'`));
  owners.push(ownerFromPath(root, "cashu", index, `m/83696968'/39'/0'/24'/3'/${index}'`));
  owners.push(ownerFromPath(root, "messages", index, `m/83696968'/39'/0'/24'/4'/${index}'`));
  owners.push(ownerFromPath(root, "transactions", index, `m/83696968'/39'/0'/24'/5'/${index}'`));
}

const result = {
  slip39: {
    wordCount: slip39.split(/\s+/).filter(Boolean).length,
    normalized: slip39,
  },
  masterSecret: {
    byteLength: masterSecret.length,
    hex: hex(masterSecret),
    base64: base64(masterSecret),
  },
  nostr: {
    path: nostrPath,
    privateKeyHex: hex(nostrPrivateKey),
    nsec: nip19.nsecEncode(nostrPrivateKey),
    publicKeyHex: nostrPublicKeyHex,
    npub: nip19.npubEncode(nostrPublicKeyHex),
  },
  cashu: {
    path: cashuPath,
    entropyHex: hex(cashuEntropy),
    mnemonic: cashuMnemonic,
    seedHex: hex(cashuSeed),
    seedBase64: base64(cashuSeed),
  },
  evolu: {
    maxIndexedLane: maxOwnerIndex,
    owners,
  },
};

console.log(JSON.stringify(result, null, 2));
'''


def read_dotenv(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")
    return {key: value or "" for key, value in dotenv_values(path).items()}


def find_bun(repo_dir: Path) -> Path:
    portable = repo_dir / ".tools" / "bun" / "bun-windows-x64" / "bun.exe"
    if portable.exists():
        return portable
    return Path("bun")


def default_repo_dir(script_dir: Path) -> Path:
    local_checkout = script_dir / "linky-main"
    if local_checkout.exists():
        return local_checkout
    return script_dir.parent / "linky-main"


def build_env(base_env: Dict[str, str], repo_dir: Path, payload: Dict[str, object]) -> Dict[str, str]:
    env = dict(base_env)
    node_dir = repo_dir / ".tools" / "node" / "node-v22.12.0-win-x64"
    bun_dir = repo_dir / ".tools" / "bun" / "bun-windows-x64"
    path_parts = []
    if node_dir.exists():
        path_parts.append(str(node_dir))
    if bun_dir.exists():
        path_parts.append(str(bun_dir))
    system_root = env.get("SystemRoot", r"C:\Windows")
    path_parts.extend([str(Path(system_root) / "System32"), system_root])
    existing_path = env.get("PATH") or env.get("Path")
    if existing_path:
        path_parts.append(existing_path)
    env["PATH"] = os.pathsep.join(path_parts)
    env["Path"] = env["PATH"]
    env["TEMP"] = str(TMP_DIR)
    env["TMP"] = str(TMP_DIR)
    env["BUN_INSTALL_CACHE_DIR"] = str(repo_dir / ".tools" / "bun" / "install-cache")
    env["npm_config_cache"] = str(NPM_CACHE_DIR)
    env["PIP_CACHE_DIR"] = str(PIP_CACHE_DIR)
    env["LINKY_KEYS_INPUT_JSON"] = json.dumps(payload, ensure_ascii=False)
    return env


def run_deriver(repo_dir: Path, slip39: str, max_owner_index: int) -> Dict[str, object]:
    bun = find_bun(repo_dir)
    payload = {"slip39": slip39, "maxOwnerIndex": max_owner_index}
    env = build_env(os.environ, repo_dir, payload)
    command = [str(bun), "--eval", JS_DERIVER]
    completed = subprocess.run(
        command,
        cwd=repo_dir / "apps" / "web-app",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Bun key derivation failed\n"
            f"exit code: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def section(title: str) -> str:
    return f"\n## {title}\n"


def format_output(data: Dict[str, object], env_path: Path, repo_dir: Path) -> str:
    lines: List[str] = []
    lines.append("# Linky Derived Keys")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Input .env: {env_path}")
    lines.append(f"Repo used for libraries: {repo_dir}")
    lines.append("")
    lines.append("WARNING: This file contains real secret material if the input mnemonic is real.")
    lines.append("Do not commit it, paste it into chats, or upload it anywhere.")

    slip39 = data["slip39"]
    master = data["masterSecret"]
    nostr = data["nostr"]
    cashu = data["cashu"]
    evolu = data["evolu"]

    lines.append(section("Input SLIP-39"))
    lines.append(f"wordCount: {slip39['wordCount']}")
    lines.append(f"normalized: {slip39['normalized']}")

    lines.append(section("Master Secret"))
    lines.append(f"byteLength: {master['byteLength']}")
    lines.append(f"hex: {master['hex']}")
    lines.append(f"base64: {master['base64']}")

    lines.append(section("Nostr"))
    lines.append(f"path: {nostr['path']}")
    lines.append(f"privateKeyHex: {nostr['privateKeyHex']}")
    lines.append(f"nsec: {nostr['nsec']}")
    lines.append(f"publicKeyHex: {nostr['publicKeyHex']}")
    lines.append(f"npub: {nostr['npub']}")

    lines.append(section("Cashu"))
    lines.append(f"path: {cashu['path']}")
    lines.append(f"entropyHex: {cashu['entropyHex']}")
    lines.append(f"mnemonic: {cashu['mnemonic']}")
    lines.append(f"seedHex: {cashu['seedHex']}")
    lines.append(f"seedBase64: {cashu['seedBase64']}")

    lines.append(section("Evolu Owners"))
    lines.append(f"maxIndexedLane: {evolu['maxIndexedLane']}")
    for owner in evolu["owners"]:
        lines.append("")
        lines.append(f"[{owner['role']}:{owner['index']}]")
        lines.append(f"path: {owner['path']}")
        lines.append(f"entropyHex: {owner['entropyHex']}")
        lines.append(f"mnemonic: {owner['mnemonic']}")
        if owner.get("ok"):
            lines.append(f"ownerId: {owner['ownerId']}")
        else:
            lines.append(f"ownerError: {owner.get('error', 'unknown')}")

    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    script_dir = Path(__file__).resolve().parent
    default_repo = default_repo_dir(script_dir)
    default_env = script_dir / ".env"
    default_out = script_dir / "linky_keys.txt"

    parser = argparse.ArgumentParser(description="Derive Linky keys from LINKY_MASTER_MNEMO in .env")
    parser.add_argument("--env", default=str(default_env), help="Path to .env file")
    parser.add_argument("--repo", default=str(default_repo), help="Path to linky-main repo")
    parser.add_argument("--out", default=str(default_out), help="Output text file")
    parser.add_argument(
        "--max-owner-index",
        type=int,
        default=DEFAULT_OWNER_MAX_INDEX,
        help="Highest indexed Evolu owner lane to derive for contacts/cashu/messages/transactions",
    )
    args = parser.parse_args(argv)
    print_secrets_to_terminal = ask_print_secrets_to_terminal()

    env_path = Path(args.env).resolve()
    repo_dir = Path(args.repo).resolve()
    out_path = Path(args.out).resolve()
    max_owner_index = max(0, int(args.max_owner_index))

    print("Linky key derivation helper")
    print(f"- reading env: {env_path}")
    print(f"- using repo:   {repo_dir}")
    print(f"- output file:  {out_path}")
    print(f"- owner lanes:  0..{max_owner_index}")

    values = read_dotenv(env_path)
    slip39 = values.get(MASTER_ENV_KEY, "").strip()
    if not slip39:
        raise RuntimeError(f"Missing {MASTER_ENV_KEY} in {env_path}")

    word_count = len([word for word in slip39.split() if word])
    print(f"- {MASTER_ENV_KEY}: found {word_count} words")
    print("- deriving via Bun and Linky dependencies...")

    data = run_deriver(repo_dir, slip39, max_owner_index)
    text = format_output(data, env_path, repo_dir)
    out_path.write_text(text, encoding="utf-8")

    print("- done")
    print(f"- wrote: {out_path}")
    print("\nThe output contains secret material. Keep it out of git and chats.")
    if print_secrets_to_terminal:
        print("\n--- BEGIN SECRET EXPORT ---")
        print(text)
        print("--- END SECRET EXPORT ---")
    else:
        print("Secrets were not printed to the terminal. Read the export file locally if needed.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
