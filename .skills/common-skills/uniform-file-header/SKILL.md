---
name: uniform-file-header
description: Add a standardized file header to newly created source or script files. Use when creating a new .c, .h, .m, .py, .cpp, or any user-specified source file, or when the user asks to add or update a file header or license banner. Automatically applies language-appropriate comment syntax, defaults the license section to MIT, preserves the exact project metadata layout, and asks only when project name/link or author/email cannot be inferred from context.
---

# Uniform File Header

## Use This Skill

Apply this skill whenever creating a new source or script file, especially:

- `.c`
- `.h`
- `.m`
- `.py`
- `.cpp`
- Any other language or script format explicitly requested by the user

Also apply it when the user asks to add, replace, or standardize a file header.

## Required Workflow

1. Determine the target file name, language, and comment syntax before writing code.
2. Insert the header at the very top of the new file before any code.
3. Default the license block to MIT unless the user explicitly requests another license.
4. Copy the license block and file-information block using the exact layout from [reference.md](reference.md). Do not reflow, paraphrase, or redesign the template.
5. Fill metadata from context when available:
   - `Project:` known repository or product name, including project URL when known
   - `File:` target file name
   - `Author:` known author name and email
   - `Date:` current date in `YYYY-MM-DD`
   - `Version:` default `0.1.0` for a new file unless context clearly implies another starting version
   - `Description:` concise, context-aware summary of the file's purpose
6. If project name/link is unknown, ask the user.
7. If author name/email is unknown, ask the user.
8. Do not ask for comment syntax for the default formats. Infer it automatically.
9. If the user specifies another language or file type, infer the correct comment syntax automatically and still apply the same header structure.

## Comment Syntax Rules

Use line comments when the language supports them:

- `.m` -> `%`
- `.py` -> `#`
- `.c`, `.h`, `.cpp` -> `//`

For other file types, infer the idiomatic comment syntax from the language:

- Prefer a single-line comment token repeated on every line when available.
- If the language only supports block comments, wrap the same internal text in the language's standard block-comment form while preserving line order, blank lines, labels, and alignment as closely as the syntax allows.
- Do not ask the user for the comment token unless the language itself is ambiguous and cannot be inferred from the requested file type.

## License Rules

- Default license: MIT
- Default SPDX short identifier: `MIT`
- For MIT, use the exact bilingual license block from [reference.md](reference.md)
- If the user specifies another license, replace the license section with the corresponding license notice and SPDX identifier while preserving:
  - the top and bottom separator lines
  - blank-line positions
  - the file-information section layout
  - the metadata field labels and alignment

If the repository already contains an established header for the requested license, follow that project pattern first. Otherwise use the official license notice.

## Metadata Rules

Infer metadata from the immediate context before asking:

- Read nearby files in the same repository when needed to discover the project name, project URL, author name, or author email.
- Reuse an existing repository header style when present.
- If the context clearly identifies project and author from git config, use those values directly.
- If either project or author information is still unknown after checking context, ask the user only for the missing fields.

## Description Formatting Rules

- Keep the `Description:` label and value alignment exactly as shown in [reference.md](reference.md).
- Write a short, concrete description based on the file's actual role.
- If the description exceeds one line, continue on the next line with the exact continuation indent from the reference template.
- Do not change the label names, colon positions, or separator widths.

## Quality Check

Before finalizing the file, verify:

- The header is the first content in the file
- The comment prefix matches the target language
- The license is MIT unless the user requested another license
- The file-information block matches the reference layout exactly
- `File`, `Date`, `Version`, and `Description` are filled
- `Project` and `Author` are filled from context or were explicitly requested from the user

## Additional Resource

- For the exact MIT template, alignment, and comment-style examples, read [reference.md](reference.md)
