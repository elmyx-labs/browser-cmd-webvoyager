"""Codex as the actor: the same prompt, skill and browser-cmd as the Claude Code actor,
in a Codex home of its own so nothing of the user's configuration reaches the model."""
import json
from pathlib import Path

# Features that add model-visible tools beyond the shell, file edits, images and web search.
DISABLED = ['goals', 'multi_agent', 'multi_agent_v2', 'image_generation', 'plugins', 'apps', 'remote_plugin',
            'browser_use', 'browser_use_external', 'computer_use', 'in_app_browser', 'tool_suggest', 'skill_search',
            'sleep_tool', 'memories']
# Skills Codex discovers from the user's home whatever CODEX_HOME is.
PERSONAL_SKILLS = [Path.home() / '.agents' / 'skills', Path.home() / '.codex' / 'skills']
LIMIT_WORDS = ('usage limit', 'rate limit', 'too many requests')


def home(root):
    """A fresh CODEX_HOME holding only a link to the signed-in account."""
    path = root / 'codex'
    path.mkdir()
    (path / 'auth.json').symlink_to(Path.home() / '.codex' / 'auth.json')
    return path


def settings(args):
    personal = [f'{{path={json.dumps(str(skill.resolve()))},enabled=false}}'
                for folder in PERSONAL_SKILLS for skill in sorted(folder.glob('*/SKILL.md'))]
    values = {
        'model_reasoning_effort': json.dumps(args.effort), 'model_reasoning_summary': '"detailed"',
        'web_search': '"live"' if args.web_tools else '"disabled"', 'approval_policy': '"never"',
        # The shell reaches the task's daemon on loopback and needs its token.
        'sandbox_mode': '"workspace-write"', 'sandbox_workspace_write.network_access': 'true',
        'shell_environment_policy.ignore_default_excludes': 'true',
        # Subscription models are code-mode only: tools reach them through the code-mode host.
        'features.code_mode_host': 'true',
        'skills.bundled.enabled': 'false', 'skills.config': f'[{",".join(personal)}]',
        **{f'features.{name}': 'false' for name in DISABLED if not (args.subagents and name == 'multi_agent')},
    }
    if args.auto_compact:
        values['model_auto_compact_token_limit'] = str(args.auto_compact)
    if getattr(args, 'fast', False):
        values['service_tier'] = '"priority"'
    return [part for key, value in values.items() for part in ('-c', f'{key}={value}')]


def command(args, prompt, last):
    return ['codex', 'exec', '--json', '--skip-git-repo-check', '-m', args.model, '--output-last-message', str(last),
            *settings(args), prompt]


def resume(args, thread, prompt, last):
    """The same session continued with one more user message, as a blocking stop hook does."""
    return ['codex', 'exec', 'resume', '--json', '--skip-git-repo-check', '-m', args.model,
            '--output-last-message', str(last), *settings(args), thread, prompt]


def summary(transcript):
    """Thread id, token usage, last message and failure of a Codex --json transcript. Each
    turn.completed carries the thread's running total, so the last one is the whole."""
    thread, usage, message, failure = None, {}, '', None
    for line in transcript.read_text().splitlines() if transcript.exists() else []:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind, item = event.get('type'), event.get('item') or {}
        if kind == 'thread.started':
            thread = event.get('thread_id')
        elif kind == 'turn.completed':
            usage = dict(event.get('usage', {}))
        elif kind == 'item.completed' and item.get('type') == 'agent_message':
            message = item.get('text', '')
        elif kind in ('turn.failed', 'error'):
            failure = str((event.get('error') or {}).get('message') or event.get('message') or kind)
    limited = bool(failure) and any(word in failure.lower() for word in LIMIT_WORDS)
    return {'thread': thread, 'usage': usage, 'result': message.strip(), 'failure': failure, 'rate_limited': limited}
