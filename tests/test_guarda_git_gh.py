"""Guarda: Git só para leitura e nenhum uso do GitHub CLI fora do modo manutenção."""
from __future__ import annotations

import pytest

import guarda

LEITURA = [
    "git status", "git log --oneline -5", "git diff HEAD~1", "git show HEAD",
    "git -c core.pager=cat log", "git --no-pager diff", "git branch", "git branch -a",
    "git branch --show-current", "git tag", "git tag -l v*", "git tag -n", "git remote -v",
    "git remote get-url origin", "git config --get user.name", "git config --list --show-origin",
    "git rev-parse HEAD", "git describe --tags", "git status | grep x", "echo 'gh' ",
    'powershell -Command "git status"', "bash -c 'git log -1'",
]
ESCRITA = [
    "git push origin main", "git tag v9.9.9", "git tag -a v9.9.9 -m x", "git tag -d v1.0.0",
    "git tag -l v* -d", "git push origin v9.9.9", "git commit -am x", "git add .",
    "git remote set-url origin https://e.com/x.git", "git remote add x https://e.com",
    "git config user.email a@b", "git config --global --unset credential.helper",
    "git config --get x --add", "git branch -D main", "git merge x", "git rebase main",
    "git fetch", "git pull", "git reset --hard", "git -C . push", "git",
    "gh pr merge 1 --merge", "gh release create v9", "gh api -X DELETE repos/x/y/rulesets/1",
    "gh auth status", "& gh.exe repo view", "echo oi && git push", "git status; git push",
    "FOO=1 git push", '& "git.exe" push', "cmd /c git push",
    'powershell -NoProfile -Command "git push"', "bash -c 'gh pr merge 1'", 'pwsh -c "git status; git tag v9"',
]


@pytest.mark.parametrize("comando", LEITURA)
def test_leitura_liberada(fora_da_manutencao, comando):
    guarda.verificar_comando(comando)


@pytest.mark.parametrize("comando", ESCRITA)
def test_escrita_bloqueada(fora_da_manutencao, comando):
    with pytest.raises(guarda.Bloqueio):
        guarda.verificar_comando(comando)


@pytest.mark.parametrize("comando", ["cmd /c git push", 'powershell -NoProfile -Command "git push"',
                                     "bash -c 'gh pr merge 1'"])
def test_shell_aninhado_bloqueado_pela_regra_de_git(comando):
    with pytest.raises(guarda.Bloqueio, match="git|GitHub"):
        guarda.verificar_git_gh(comando)


@pytest.mark.parametrize("comando", [c for c in LEITURA + ESCRITA if not c.startswith("cmd /c")])
def test_modo_manutencao_libera(em_manutencao, comando):
    guarda.verificar_comando(comando)
