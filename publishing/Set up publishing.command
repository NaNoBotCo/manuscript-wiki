#!/bin/bash
# ============================================================================
#  Set up publishing — connect the Lanna Wiki to your GitHub Pages site.
#  Double-click this ONCE. It walks you through the only step Claude can't do
#  for you: signing in to GitHub. After this, refreshes are automatic.
#
#  It will:
#    1. make sure the GitHub CLI is installed
#    2. sign you in to GitHub  (a browser window opens — YOU approve it)
#    3. connect your site repo  NaNoBotCo/Lanna  (creates it if missing)
#    4. do the first publish    (build + push the whole wiki)
#    5. turn on GitHub Pages     (serving from  main /docs )
#  When it finishes it prints your public address:  https://nanobotco.github.io/Lanna/
# ============================================================================
set -uo pipefail

OWNER="NaNoBotCo"
REPO="Lanna"
SLUG="$OWNER/$REPO"
SITE_REPO="${SITE_REPO:-$HOME/Developer/claude code projects/nanobotco-lanna}"
WIKI_DIR="$HOME/Developer/claude code projects/manuscript-wiki"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

say() { echo; echo "── $* ──"; }
die() { echo; echo "STOPPED: $*"; echo "Nothing was published. Fix the above and double-click again."; sleep 30; exit 1; }

# 1. GitHub CLI ---------------------------------------------------------------
say "1/5  Checking the GitHub CLI"
if ! command -v gh >/dev/null 2>&1; then
  echo "Installing the GitHub CLI (gh) via Homebrew…"
  command -v brew >/dev/null 2>&1 || die "Homebrew isn't installed. Install it from https://brew.sh then retry."
  brew install gh || die "Could not install gh."
fi
echo "gh $(gh --version | head -1 | awk '{print $3}') ready."

# 2. Sign in ------------------------------------------------------------------
say "2/5  Signing in to GitHub"
if gh auth status >/dev/null 2>&1; then
  echo "Already signed in as: $(gh api user -q .login 2>/dev/null)"
else
  echo "A browser window will open. Approve the sign-in there, as $OWNER."
  gh auth login --hostname github.com --git-protocol https --web || die "Sign-in didn't complete."
fi
gh auth setup-git >/dev/null 2>&1 || true   # let git push over https use your gh login

# 3. Repo ---------------------------------------------------------------------
say "3/5  Your site repository"
if [ -d "$SITE_REPO/.git" ]; then
  echo "Using existing local clone: $SITE_REPO"
elif gh repo view "$SLUG" >/dev/null 2>&1; then
  echo "Repo $SLUG exists on GitHub — cloning it."
  gh repo clone "$SLUG" "$SITE_REPO" || die "Could not clone $SLUG."
else
  echo "Creating public repo $SLUG and cloning it…"
  gh repo create "$SLUG" --public --description "Lanna Manuscript Wiki — public snapshot" >/dev/null 2>&1 || true
  gh repo clone "$SLUG" "$SITE_REPO" || die "Could not clone $SLUG (does it exist and are you signed in as $OWNER?)."
fi

# commit identity for the automated commits (public no-reply, keeps your email private)
cd "$SITE_REPO" || die "Missing $SITE_REPO"
git config user.name  "$OWNER"
git config user.email "$OWNER@users.noreply.github.com"

# 4. First publish ------------------------------------------------------------
say "4/5  First publish (this builds the whole site and pushes it — a few minutes)"
SITE_REPO="$SITE_REPO" bash "$WIKI_DIR/publishing/publish_site.sh" || die "The first publish failed (see messages above)."

# 5. Turn on Pages ------------------------------------------------------------
say "5/5  Turning on GitHub Pages (main /docs)"
if gh api "repos/$SLUG/pages" >/dev/null 2>&1; then
  echo "Pages already enabled."
else
  if gh api --method POST "repos/$SLUG/pages" \
       -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1; then
    echo "Pages enabled."
  else
    echo "Couldn't enable Pages automatically. Do it once by hand:"
    echo "  → https://github.com/$SLUG/settings/pages"
    echo "    Source: Deploy from a branch · Branch: main · Folder: /docs · Save"
  fi
fi

echo
echo "============================================================"
echo "  Done. Your public wiki will be live in a minute or two at:"
echo "      https://nanobotco.github.io/Lanna/"
echo "  From now on it refreshes on its own (see the LaunchAgent)."
echo "============================================================"
sleep 20
