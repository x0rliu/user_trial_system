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
