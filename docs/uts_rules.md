UTS_Working_Rules:
  version: "v3"
  intent: >
    Favor clarity, explicitness, and debuggability over elegance.
    Anything that makes tracing behavior harder is a regression.

  collaboration_rules:
    - id: 1
      name: "Me 1 / You 1"
      rule: "One move at a time. No parallel work."

    - id: 2
      name: "Before / After only"
      rule: >
        Every change must show exact code before and after.
        If it is not copy-pasteable, it does not count.

    - id: 3
      name: "Always name the file"
      rule: >
        Every change must state the exact file path and what calls it.

    - id: 4
      name: "No guessing"
      rule: >
        If something is not shown, ask to see it.
        Never assume structure, intent, or behavior.

    - id: 5
      name: "If no before, say exactly where it goes"
      rule: >
        File, function, and insertion point must be explicit.
        No ambiguity.

  architectural_rules:
    - id: 6
      name: "DB is the source of truth"
      rule:
        get_never_mutates: true
        ui_can_lie: true
        cache_is_temporary: true

    - id: 7
      name: "No re-architecture unless asked"
      rule: >
        The design is correct.
        Fix implementation only.

    - id: 8
      name: "Routing is explicit and boring"
      rule:
        routing_location: "main.py"
        matching: "exact string only"
        forbidden:
          - startswith
          - implicit dispatch
          - automatic routing
          - clever abstractions

    - id: 9
      name: "State must be explicit and resumable"
      rule:
        partial_users_are_valid: true
        drafts_are_valid: true
        inferred_state: false
        silent_transitions: false

  response_discipline:
    - id: 10
      name: "End with what file next"
      rule: >
        Every response must either name the next file to touch
        or explicitly say STOP.

  post_routing_rules:
    - id: 11
      name: "POST routing structure"
      rule:
        location: "main.py"
        pattern: |
          if self.path == "/example/path":
              self._handle_example_post()
              return
        naming_convention: "_handle_*"
        placement: "defined later in the same file"
        responsibilities:
          - validate_auth
          - validate_input
          - mutate_state
          - redirect
        rendering_allowed: false
        delegation_allowed_to: "handlers/*.py"

      example_format_only:
        note: "Format example only. Not logic."
        code: |
          # -------------------------
          # Product Team Request Trial (POST)
          # -------------------------
          def _handle_request_trial_create(self):
              ...

  get_routing_rules:
    - id: 12
      name: "GET routing structure"
      rule:
        location: "main.py"
        pattern: |
          if path == "example/path":
              self._render_example()
              return
        naming_convention: "_render_*"
        responsibilities:
          - validate_auth
          - validate_query_params
          - delegate_to_handlers
          - send_html_or_redirect
        page_construction_location: "handlers/*.py"
        main_py_builds_html: false

  mental_model:
    main_py: "Explicit, boring traffic cop"
    handle_functions: "POST mutation + redirect only"
    render_functions: "GET validation + delegation"
    handlers_py: "Page construction and lifecycle logic"
    priorities:
      - explicit_over_clever
      - debuggable_over_elegant


uts_working_rules:
  product_team_layout_contract:
    intent: >
      Product Team pages must follow a consistent 2-layer layout contract so that
      routing remains boring, rendering is predictable, and rails never "disappear"
      due to ad-hoc template mixing.

    templates:
      outer_shell:
        file: app/templates/product_team/base_product_team.html
        responsibility:
          - Provides the Product Team "site shell" (header/nav + footer/legal)
          - Hosts the single placeholder token for body insertion
          - Does NOT contain wizard logic
          - Does NOT contain rails
        rule: >
          All Product Team pages MUST render inside base_product_team.html as the outer shell.

      inner_layout:
        file: app/templates/product_team/product_layout.html
        responsibility:
          - Defines the 3-column structure:
              - left_rail
              - center_content
              - right_summary
          - Exposes placeholders/tokens for injection:
              - "{{ PRODUCT_LEFT_RAIL }}"
              - "{{ PRODUCT_WIZARD_STATUS }}"
              - "{{ PRODUCT_CONTENT }}"
              - "{{ PRODUCT_SUMMARY }}"
        rule: >
          All Product Team pages MUST use product_layout.html inside the base shell.

    renderer_contract:
      assembly_order:
        - build_left_rail_html: required
        - build_wizard_status_html: optional
        - build_main_content_html: required
        - build_summary_html: optional
        - inject_into_product_layout: required
        - inject_product_layout_into_base_shell: required
        - inject_nav_user_anchor: required
      hard_rules:
        - never_render_center_content_directly_into_global_base: true
        - never_skip_product_layout_for_any_product_team_page: true
        - rails_must_be_defined_in_renderer_not_in_main_py: true
        - renderer_builds_html_only_get_never_mutates: true

    naming_conventions:
      get_renderers:
        prefix: render_
        examples:
          - render_product_request_trial_get
          - render_product_request_trial_wizard_get
          - render_product_request_trial_pending_get
      post_handlers:
        prefix: handle_
        examples:
          - handle_product_request_trial_wizard_basics_post
          - handle_product_request_trial_submit_post

    prohibited_patterns:
      - injecting_partial_html_directly_into_base_template_without_product_layout
      - building_rails_inside_app/main.py
      - mixing_non_product_team_templates_into_product_team_pages
      - creating_step_specific_templates_unless_explicitly_intended_and_present

    definition_of_done_for_any_product_team_page:
      - uses_base_product_team_html: true
      - uses_product_layout_html: true
      - left_rail_present: true
      - center_content_present: true
      - right_summary_present_or_intentionally_blank: true
      - nav_user_anchor_present: true

  changelog_rules:
    intent: >
      Changelogs and progress summaries must preserve continuity across sessions,
      make completed work easy to audit, and clearly separate confirmed work from
      assumptions, deferred cleanup, and next steps.

    required_when:
      - end_of_work_session
      - before_switching_major_priority
      - after_large_multi-step_slice
      - when_user_asks_for_progress_or_changelog
      - before_starting_security_or_IT_review_pass

    output_modes:
      formal_changelog_entry:
        use_when:
          - "User asks for a changelog update"
          - "User asks for the changelog in the same format as yesterday"
          - "Work should be copied into docs/changelog.md"
        rule: >
          Use the docs/changelog.md chronological entry format exactly.
          Do not use priority tables, progress snapshot tables, or extra summary
          sections unless the user separately asks for a progress summary.

      progress_summary:
        use_when:
          - "User asks where we are"
          - "User asks for the priority list"
          - "User asks for progress"
          - "User asks what is next"
        rule: >
          Use concise tables and current-state tracking. This is not the same as
          a formal changelog entry.

    format_contract:
      formal_changelog_entries:
        heading_format: "### YYYY-MM-DD — Short descriptive title"
        order: "newest entries first"
        please give this changelog to me in MD formatting
        markdown_style: >
          Each required section must be rendered as a blockquote section using
          bold section labels, matching the established docs/changelog.md style.
        required_sections_in_order:
          - Summary
          - Changes Made
          - Confirmed Working
          - Design Decisions
          - Untested / Needs Follow-up
          - Known Exceptions / Deferred Cleanup
          - Next Recommended Step
        exact_template: |
          ### YYYY-MM-DD — Short descriptive title

          > **Summary**  
          > One concise paragraph summarizing the session or work slice.
          >
          > **Changes Made**
          > - Change 1.
          > - Change 2.
          > - Change 3.
          >
          > **Confirmed Working**
          > - Confirmed item 1.
          > - Confirmed item 2.
          >
          > **Design Decisions**
          > - Decision 1.
          > - Decision 2.
          >
          > **Untested / Needs Follow-up**
          > - Follow-up 1.
          > - Follow-up 2.
          >
          > **Known Exceptions / Deferred Cleanup**
          > - Deferred item 1.
          > - Deferred item 2.
          >
          > **Next Recommended Step**  
          > State the exact next recommended step.

      progress_summary_entries:
        required_sections_in_order:
          - Top priorities table
          - Current priority progress table
          - Sub-slice progress table when applicable
          - Key accomplishments
          - Important fixes verified
          - Current stopping point
          - Next recommended step
        rule: >
          Progress summaries may use tables. Formal changelog entries should not
          be turned into progress-summary tables unless the user asks for both.

    status_language:
      allowed_statuses:
        - "✅ Done"
        - "✅ Complete"
        - "✅ Complete enough for MVP"
        - "✅ Passed"
        - "🟡 In progress"
        - "🟡 Started"
        - "⏭️ Next"
        - "Not started"
        - "Deferred"
        - "Blocked"
      rule: >
        Status labels must be specific and honest. Do not mark work complete
        unless it was compiled, smoke-tested, audited, confirmed by SQL output,
        UI-confirmed by the user, or otherwise explicitly confirmed.

    evidence_rules:
      confirmed_work: >
        Only list work under Confirmed Working or Important fixes verified if
        the user confirmed it, py_compile passed, SQL output confirmed it, the UI
        was smoke-tested, or an audit returned clean.
      assumed_work: >
        If something is believed to be done but not tested, it must go under
        Untested / Needs Follow-up, not Confirmed Working.
      deferred_work: >
        Known technical debt must be listed explicitly under Known Exceptions /
        Deferred Cleanup. Do not hide deferred work inside positive summaries.

    wording_rules:
      - "Formal changelog entries must use the established blockquote format."
      - "Progress summaries may use concise tables."
      - "Do not mix the formal changelog format with the progress-summary format unless the user asks for both."
      - "Keep the current stopping point explicit when giving progress summaries."
      - "Always include the next recommended step."
      - "Do not collapse unrelated workstreams into one vague status."
      - "Do not say complete when the correct status is complete enough for MVP."
      - "Do not invent dates, tests, commits, or confirmations."

    continuity_rules:
      - "Carry forward the active priority number and slice label."
      - "Preserve completed slice labels exactly when possible."
      - "Record commit points and suggested commit messages when relevant."
      - "If a new workstream is inserted before the next numbered priority, label it clearly, such as 5D."
      - "When resuming, state the last completed slice and the next slice."

    changelog_storage:
      canonical_file: "docs/changelog.md"
      rule: >
        Formal changelog entries should be added to docs/changelog.md using
        newest-first order. Chat progress summaries may use the same factual
        content but do not replace the canonical changelog unless the user asks.

    examples_reference:
      rule: >
        The canonical changelog style is the existing docs/changelog.md format:
        dated heading, blockquoted section labels, bullet lists for details, and
        a final explicit Next Recommended Step.