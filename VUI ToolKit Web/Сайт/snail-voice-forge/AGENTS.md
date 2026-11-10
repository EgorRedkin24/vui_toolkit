<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Architecture

- Keep all REST access in `src/lib/vui-api.ts`; UI code must use its helpers so API URL precedence and error parsing stay consistent.
- Use one dynamic `/tools/$toolId` route with shared job execution UI and dedicated form components to keep polling and result behavior identical.
- Fetch API reference lists independently after a successful health check so one failed endpoint does not hide unrelated presets, effects, or forms.
