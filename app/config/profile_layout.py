BASIC_PROFILE_SECTIONS = [
    {
        "id": "gaming",
        "title": "Gaming & Entertainment",
        "collapsible": True,
        "categories": [1, 2, 3, 4, 22],
        "selection_mode": {
            1: "single",  # PC Gamer → radio
            2: "single",  # Console Gamer → radio
            3: "single",  # Streamer → radio
            4: "single",  # Content Creator → radio
            22: "multi",  # Consoles owned → checkbox
        }
    },
    {
        "id": "work",
        "title": "Work Context",
        "collapsible": True,

        # New numeric work context (days per week)
        "categories": [
            36,  # Work from home (days/week)
            37,  # Fixed desk office (days/week)
            38,  # Flex desk office (days/week)
            39,  # Public spaces (days/week)
            26,  # Zoom Calls
        ],

        "selection_mode": {
            36: "single",
            37: "single",
            38: "single",
            39: "single",
            26: "single",
        },
    },
    {
        "id": "devices",
        "title": "Devices & Platforms",
        "collapsible": True,
        "categories": [9, 10, 11],
        "selection_mode": {
            9: "multi",  # Computer Type → radio
            10: "multi",  # Computer OS → radio
            11: "multi",  # Phone OS → radio

        },
    },
    {
        "id": "peripherals",
        "title": "Peripherals & Setup",
        "collapsible": True,
        "categories": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
        "default_collapsed": True,
        "selection_mode": {
            12: "single",  # Monitor → radio
            13: "multi",  # Keyboard → radio
            14: "single",  # Speakers → radio
            15: "multi",  # Headset → radio
            16: "multi",  # Earbuds → radio
            17: "multi",  # Microphone → radio
            18: "multi",  # webcam → radio
            19: "single",  # Docking station → radio
            20: "multi",  # Mouse → radio
            21: "single",  # Touchpad → radio

        },
    },
    {
        "id": "trial",
        "title": "Trial Preferences",
        "collapsible": False,
        "categories": [23],
        "selection_mode": {
            23: "single",  # Trial Type → radio
        },
    },
]

ADVANCED_PROFILE_SECTIONS = [
    {
        "id": "job",
        "title": "Job & Professional Context",
        "categories": [25],
        "selection_mode": {
            25: "single",
        },
    },
    {
        "id": "physical_fit",
        "title": "Physical Fit & Ergonomics",
        "categories": [
            27,  # Head Width
            28,  # Head Length
            29,  # Hand Size
        ],
        "selection_mode": {
            27: "single",
            28: "single",
            29: "single",
        },
    },
    {
        "id": "hair",
        "title": "Hair Characteristics",
        "categories": [
            30,  # Hair Volume
            31,  # Hair Type
        ],
        "selection_mode": {
            30: "single",
            31: "single",
        },
    },
    {
        "id": "glasses",
        "title": "Vision & Glasses",
        "categories": [
            32,  # Glasses Frequency
        ],
        "selection_mode": {
            32: "single",
        },
    },
    {
        "id": "ear_piercings",
        "title": "Ear Piercings",
        "categories": [
            33,  # Ear Piercing Frequency
            34,  # Ear Piercing Locations
        ],
        "selection_mode": {
            33: "single",
            34: "multi",
        },
    },
    {
        "id": "handedness",
        "title": "Hand Dominance",
        "categories": [
            35,  # Hand Dominance
        ],
        "selection_mode": {
            35: "single",
        },
    },
]

INTEREST_PROFILE_SECTIONS = [

    # --------------------------------------------------
    # Brand Interest
    # --------------------------------------------------
    {
        "id": "brands",
        "title": "Brand Interests",
        "description": "Which Logitech brands are you generally interested in?",
        "collapsible": False,
        "categories": [101],
        "selection_mode": {
            101: "multi",  # Brands are always multi-interest
        },
    },

    # --------------------------------------------------
    # Product Categories (Top-Level)
    # --------------------------------------------------
    {
        "id": "product_types",
        "title": "Product Types",
        "description": (
            "Select the types of products you're interested in. "
            "If you select a category, we’ll assume you’re open to all options unless you deselect some."
        ),
        "collapsible": False,
        "categories": [102],          # ✅ REQUIRED so triggers can be fetched/rendered
        "selection_mode": {102: "multi"},  # ✅ Optional but consistent
    },

    # --------------------------------------------------
    # Product Tier
    # --------------------------------------------------
    {
        "id": "tiers",
        "title": "Product Tiers",
        "description": (
            "What general product tiers are you interested in testing?"
        ),
        "collapsible": False,
        "categories": [103],
        "selection_mode": {
            103: "multi",  # Entry / Mid / High
        },
    },

    # --------------------------------------------------
    # Mobility / Education Context
    # --------------------------------------------------
    {
        "id": "mobility",
        "title": "Mobility & Education Context",
        "description": (
            "Are you interested in products designed for education, mobility, or on-the-go use?"
        ),
        "collapsible": True,
        "categories": [1001],
        "selection_mode": {
            1001: "multi",
        },
    },

    # --------------------------------------------------
    # Keyboard Interests
    # (only shown if PT102a selected)
    # --------------------------------------------------
    {
        "id": "keyboard_details",
        "title": "Keyboard Preferences",
        "parent_product_type": "PT102a",
        "collapsible": True,
        "categories": [201, 202, 203],
        "selection_mode": {
            201: "multi",  # Mechanical / Non
            202: "multi",  # Wired / Wireless
            203: "multi",  # Form factor
        },
    },

    # --------------------------------------------------
    # Mouse Interests
    # --------------------------------------------------
    {
        "id": "mouse_details",
        "title": "Mouse Preferences",
        "parent_product_type": "PT102b",
        "collapsible": True,
        "categories": [301, 302, 303],
        "selection_mode": {
            301: "multi",  # Grip
            302: "multi",  # Connection
            303: "multi",  # Style
        },
    },

    # --------------------------------------------------
    # Headset Interests
    # --------------------------------------------------
    {
        "id": "headset_details",
        "title": "Headset Preferences",
        "parent_product_type": "PT102c",
        "collapsible": True,
        "categories": [401, 402, 403, 404, 405],
        "selection_mode": {
            401: "multi",  # Fit
            402: "multi",  # Use case
            403: "multi",  # Connection
            404: "multi",  # Isolation
            405: "multi",  # Mic
        },
    },

    # --------------------------------------------------
    # Earbuds Interests
    # --------------------------------------------------
    {
        "id": "earbuds_details",
        "title": "Earbuds Preferences",
        "parent_product_type": "PT102d",
        "collapsible": True,
        "categories": [501, 502, 503],
        "selection_mode": {
            501: "multi",  # Connection
            502: "multi",  # Fit
            503: "multi",  # ANC
        },
    },

    # --------------------------------------------------
    # Speaker Interests
    # --------------------------------------------------
    {
        "id": "speakers_details",
        "title": "Speaker Preferences",
        "parent_product_type": "PT102e",
        "collapsible": True,
        "categories": [601, 602, 603],
        "selection_mode": {
            601: "multi",  # Connection
            602: "multi",  # Use
            603: "multi",  # Size
        },
    },

    # --------------------------------------------------
    # Microphone Interests
    # --------------------------------------------------
    {
        "id": "microphone_details",
        "title": "Microphone Preferences",
        "parent_product_type": "PT102f",
        "collapsible": True,
        "categories": [701, 702, 703],
        "selection_mode": {
            701: "multi",  # Connection
            702: "multi",  # Lighting
            703: "multi",  # Use
        },
    },

    # --------------------------------------------------
    # Webcam Interests
    # --------------------------------------------------
    {
        "id": "webcam_details",
        "title": "Webcam Preferences",
        "parent_product_type": "PT102g",
        "collapsible": True,
        "categories": [801, 802, 803],
        "selection_mode": {
            801: "multi",  # Face login
            802: "multi",  # Privacy
            803: "multi",  # Resolution
        },
    },

    # --------------------------------------------------
    # Creator Gear Interests
    # --------------------------------------------------
    {
        "id": "creator_gear",
        "title": "Streaming & Creator Gear",
        "parent_product_type": "PT102h",
        "collapsible": True,
        "categories": [901, 902],
        "selection_mode": {
            901: "multi",  # Gear type
            902: "multi",  # Use intent
        },
    },
]
