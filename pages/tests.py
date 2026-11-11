from django.test import TestCase


class FirstImpressionTests(TestCase):
    THIRD_PARTY = ("googleapis", "gstatic", "jsdelivr", "unpkg", "cdnjs", "google-analytics", "googletagmanager")

    def test_landing_has_share_preview_tags(self):
        html = self.client.get("/").content.decode()
        for needle in ('property="og:title"', 'property="og:description"', 'property="og:image"', 'name="twitter:card"', 'name="description"'):
            self.assertIn(needle, html)
        self.assertRegex(html, r'content="http://testserver/static/img/og-image[\w.]*\.jpg"')

    def test_pages_load_no_third_party_hosts(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        pages = ["/", "/privacy", "/auth/login", "/auth/register"]
        for url in pages:
            html = self.client.get(url).content.decode()
            for host in self.THIRD_PARTY:
                self.assertNotIn(host, html, f"{host} found on {url}")
        self.client.force_login(user)
        for url in ("/app/", "/app/charts/", "/app/compare/"):
            html = self.client.get(url).content.decode()
            for host in self.THIRD_PARTY:
                self.assertNotIn(host, html, f"{host} found on {url}")

    def test_privacy_page_is_public_and_linked_from_the_footer(self):
        response = self.client.get("/privacy")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How your data is handled")
        self.assertContains(response, "testing version")
        self.assertContains(self.client.get("/"), 'href="/privacy"')
        self.assertContains(self.client.get("/auth/register"), 'href="/privacy"')

    def test_footer_keeps_the_builder_credit_separate_from_the_product_links(self):
        html = self.client.get("/").content.decode()
        self.assertIn("site-footer__by", html)
        self.assertNotIn("Need a product like this", html)

    def test_font_and_chart_library_are_served_locally(self):
        from django.contrib.staticfiles import finders
        for path in ("fonts/manrope-latin.woff2", "fonts/manrope-latin-ext.woff2", "vendor/chart.umd.js", "img/og-image.jpg"):
            self.assertIsNotNone(finders.find(path), path)


class LandingSectionsTests(TestCase):
    def setUp(self):
        self.html = self.client.get("/").content.decode()

    def test_has_the_sections_below_the_hero(self):
        for anchor in ('id="why"', 'id="screenshots"', 'id="how-it-works"', 'id="your-data"', 'id="faq"'):
            self.assertIn(anchor, self.html)

    def test_screenshots_are_real_files_with_alt_text_and_dimensions(self):
        import re
        from django.contrib.staticfiles import finders
        imgs = re.findall(r"<img[^>]+>", self.html)
        shots = [i for i in imgs if "shots/" in i]
        self.assertEqual(len(shots), 4)  # the hero phone + three feature screenshots
        for tag in shots:
            self.assertRegex(tag, r'alt="[^"]{20,}"')
            self.assertIn("width=", tag)
            self.assertIn("height=", tag)
            if "hero" not in tag:
                self.assertIn('loading="lazy"', tag)
        self.assertIn('fetchpriority="high"', [t for t in shots if "hero" in t][0])
        for name in ("hero", "dashboard", "budgets", "goals"):
            self.assertIsNotNone(finders.find(f"img/shots/{name}.jpg"))

    def test_how_it_works_has_three_steps(self):
        self.assertEqual(self.html.count('class="glass-card step"'), 3)

    def test_faq_answers_match_what_the_app_does(self):
        self.assertEqual(self.html.count('class="glass-card faq__item"'), 11)
        self.assertIn("RON, EUR, USD or GBP", self.html)
        self.assertIn("free while it is in testing", self.html)
        self.assertIn("no automatic password reset", self.html)

    def test_public_navbar_links_to_the_sections(self):
        self.assertIn('href="/#how-it-works"', self.html)
        self.assertIn('href="/#faq"', self.html)


class LandingDemoButtonTests(TestCase):
    def test_landing_offers_the_demo_as_a_post_form(self):
        html = self.client.get("/").content.decode()
        self.assertEqual(html.count('action="/auth/demo"'), 2)  # hero + final call to action
        self.assertIn("Try the demo", html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertIn("Can I try it without signing up?", html)

    def test_privacy_page_describes_demo_accounts(self):
        self.assertContains(self.client.get("/privacy"), "Demo accounts")


class HeroFirstImpressionTests(TestCase):
    def setUp(self):
        self.html = self.client.get("/").content.decode()
        self.hero = self.html.split('id="screenshots"')[0]

    def test_hero_shows_the_real_app_not_a_drawing(self):
        self.assertIn("phone__img", self.hero)
        self.assertNotIn("phone__row", self.hero)
        self.assertIn("The real app, with example data", self.hero)

    def test_hero_uses_svg_icons_not_emoji(self):
        import re
        self.assertIsNone(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", self.hero))
        self.assertGreaterEqual(self.hero.count("<svg"), 3)

    def test_trust_row_makes_only_checkable_claims(self):
        for text in ("Each account sees only its own data", "No ads, trackers or third-party scripts", "Export to CSV, Excel or PDF anytime"):
            self.assertIn(text, self.hero)
        for vague in ("Add transactions in seconds", "what&#x27;s left at a glance", "at a glance"):
            self.assertNotIn(vague, self.hero)

    def test_wallet_claim_no_longer_suggests_a_currency_per_wallet(self):
        self.assertNotIn("Separate wallets, in RON", self.html)
        self.assertIn("Separate wallets for card, cash and savings", self.hero)


class BrandMarkTests(TestCase):
    def test_navbar_uses_the_donut_mark_and_two_weight_wordmark(self):
        html = self.client.get("/").content.decode()
        nav = html.split('<nav class="nav">')[1].split("</nav>")[0]
        self.assertEqual(nav.count("<circle"), 3)          # three donut segments
        self.assertNotIn("logoG", html)                    # the old gradient "M" square is gone
        self.assertIn('<span class="nav__my">My</span>Budget', nav)

    def test_every_icon_size_exists_and_is_linked(self):
        from django.contrib.staticfiles import finders
        html = self.client.get("/").content.decode()
        for path in ("favicon.svg", "img/favicon-32.png", "img/apple-touch-icon.png", "img/og-image.jpg"):
            self.assertIsNotNone(finders.find(path), path)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn('sizes="32x32"', html)

    def test_favicon_is_the_donut_on_a_teal_square(self):
        from django.contrib.staticfiles import finders
        svg = open(finders.find("favicon.svg")).read()
        self.assertEqual(svg.count("<circle"), 3)
        self.assertIn("<rect", svg)


class AudienceAndDifferenceTests(TestCase):
    def setUp(self):
        self.html = self.client.get("/").content.decode()
        self.hero = self.html.split('id="why"')[0]

    def test_hero_says_who_it_is_for(self):
        self.assertIn("Made for people who log their money by hand", self.hero)
        self.assertIn("without connecting a bank", self.hero)

    def test_why_section_has_three_points_and_the_limits(self):
        why = self.html.split('id="why"')[1].split('id="screenshots"')[0]
        self.assertEqual(why.count('class="glass-card why__item"'), 3)
        self.assertIn("No formulas to maintain", why)
        self.assertIn("no bank sync, uses one currency per account, and is made for one person per account", why)

    def test_faq_answers_the_bank_question_without_overclaiming(self):
        self.assertIn("Does it connect to my bank?", self.html)
        self.assertIn("nothing is pulled from your bank", self.html)

    def test_no_competitor_names_or_usage_claims(self):
        lowered = self.html.lower()
        for word in ("ynab", "mint", "excel spreadsheet", "thousands of users", "trusted by"):
            self.assertNotIn(word, lowered)


class ScreenshotTrustTests(TestCase):
    def setUp(self):
        self.html = self.client.get("/").content.decode()

    def test_feature_screenshots_open_enlarged_and_work_without_javascript(self):
        import re
        links = re.findall(r'<a class="shot-link" href="([^"]+)" data-lightbox', self.html)
        self.assertEqual(len(links), 3)
        for href in links:
            self.assertIn("/static/img/shots/", href)           # plain link to the image itself
            self.assertIn(f'src="{href}"', self.html)             # the thumbnail is the same file
        self.assertIn("Enlarge", self.html)

    def test_section_is_upfront_that_the_example_account_is_staged(self):
        self.assertIn("set up on purpose to show one warning and one over-budget category", self.html)

    def test_screenshots_can_be_refreshed_with_one_documented_command(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        script = root / "scripts" / "capture_landing_screenshots.py"
        self.assertTrue(script.exists())
        self.assertIn("Try the demo", script.read_text())
        self.assertIn("scripts/capture_landing_screenshots.py", (root / "README.md").read_text())

    def test_no_invented_social_proof(self):
        lowered = self.html.lower()
        for phrase in ("testimonial", "customers love", "★", "5 stars", "rated", "users worldwide", "trusted by"):
            self.assertNotIn(phrase, lowered)


class TrustPagesTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    # --- contact ---------------------------------------------------------
    def test_contact_page_is_public_and_saves_a_message(self):
        from .models import FeedbackMessage
        self.assertEqual(self.client.get("/contact").status_code, 200)
        response = self.client.post("/contact", {"name": "Sam", "email": "sam@example.com", "message": "The budgets page is great, one idea: dark mode."})
        self.assertRedirects(response, "/contact")
        msg = FeedbackMessage.objects.get()
        self.assertEqual((msg.name, msg.email), ("Sam", "sam@example.com"))
        self.assertIsNone(msg.user)

    def test_contact_needs_a_real_message_but_not_a_name_or_email(self):
        from .models import FeedbackMessage
        response = self.client.post("/contact", {"message": "short"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "at least a few words")
        self.assertFalse(FeedbackMessage.objects.exists())
        self.client.post("/contact", {"message": "Anonymous feedback without any contact details."})
        self.assertEqual(FeedbackMessage.objects.count(), 1)

    def test_contact_honeypot_silently_drops_bot_submissions(self):
        from .models import FeedbackMessage
        response = self.client.post("/contact", {"message": "Buy cheap watches now, click here please", "website": "http://spam.example"}, follow=True)
        self.assertContains(response, "Thanks, your message was received.")
        self.assertFalse(FeedbackMessage.objects.exists())

    def test_contact_is_rate_limited(self):
        from .models import FeedbackMessage
        for i in range(7):
            self.client.post("/contact", {"message": f"Message number {i} with enough words"})
        self.assertEqual(FeedbackMessage.objects.count(), 5)

    def test_logged_in_users_are_linked_but_demo_users_are_not(self):
        from django.contrib.auth import get_user_model
        from accounts.demo import create_demo_user
        from .models import FeedbackMessage
        real = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        self.client.force_login(real)
        self.client.post("/contact", {"message": "A message from a signed-in user."})
        self.assertEqual(FeedbackMessage.objects.get().user, real)
        FeedbackMessage.objects.all().delete()
        self.client.force_login(create_demo_user())
        self.client.post("/contact", {"message": "A message from a demo visitor here."})
        self.assertIsNone(FeedbackMessage.objects.get().user)

    def test_messages_are_readable_in_django_admin(self):
        from django.contrib.auth import get_user_model
        from .models import FeedbackMessage
        FeedbackMessage.objects.create(name="Sam", message="Hello from the form")
        admin = get_user_model().objects.create_superuser(username="boss", email="boss@example.com", password="pass12345")
        self.client.force_login(admin)
        response = self.client.get("/admin/pages/feedbackmessage/")
        self.assertContains(response, "Hello from the form")

    # --- about, what's new, footer ---------------------------------------
    def test_about_says_who_is_behind_it_without_inventing_anything(self):
        html = self.client.get("/about").content.decode()
        self.assertIn("Andreea Sandu", html)
        self.assertIn("Andreea Tech", html)
        self.assertIn("github.com/SanduAndreea22/my_budget", html)
        self.assertIn("Need a product like this for your business?", html)
        for forbidden in ("accounting", "contabil", "years of experience", "clients", "testimonial"):
            self.assertNotIn(forbidden, html.lower())

    def test_whats_new_lists_dated_changes(self):
        html = self.client.get("/whats-new").content.decode()
        self.assertIn("11 November 2026", html)
        self.assertIn("Delete your account", html)

    def test_footer_links_to_the_trust_pages_on_every_kind_of_page(self):
        for url in ("/", "/privacy", "/about", "/contact", "/auth/login"):
            html = self.client.get(url).content.decode()
            footer = html.split('class="container site-footer"')[1]
            for href in ('href="/about"', 'href="/whats-new"', 'href="/contact"', 'href="/privacy"'):
                self.assertIn(href, footer, f"{href} missing on {url}")

    # --- landing wording --------------------------------------------------
    def test_landing_repeats_testing_less_and_answers_what_comes_after(self):
        html = self.client.get("/").content.decode()
        self.assertLessEqual(html.lower().count("testing"), 3)
        self.assertIn("What happens after testing?", html)
        self.assertIn("No pricing has been decided", html)
        self.assertIn("Who builds it, and how do I reach them?", html)

    def test_private_claim_links_to_its_proof(self):
        html = self.client.get("/").content.decode()
        self.assertIn('href="/privacy#protected"', html)
        self.assertIn('id="protected"', self.client.get("/privacy").content.decode())

    def test_privacy_page_covers_who_runs_it_contact_messages_and_deletion(self):
        html = self.client.get("/privacy").content.decode()
        self.assertIn("Who runs MyBudget", html)
        self.assertIn("Messages you send through the contact form", html)
        self.assertIn("delete your account yourself", html)
        self.assertNotIn("Deleting an account is not self-service yet", html)


class AdminWorksTests(TestCase):
    """APP_DIRS was False since the first commit, so no admin page could render."""

    def test_admin_login_page_renders(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")

    def test_admin_index_renders_for_a_superuser_and_lists_the_contact_inbox(self):
        from django.contrib.auth import get_user_model
        boss = get_user_model().objects.create_superuser(username="boss", email="boss@example.com", password="pass12345")
        self.client.force_login(boss)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback messages")


class NavigationAndFooterCopyTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_public_navbar_uses_verbs_and_matching_names(self):
        nav = self.client.get("/").content.decode().split('<nav class="nav">')[1].split("</nav>")[0]
        self.assertIn(">Log in<", nav)
        self.assertNotIn(">Login<", nav)
        self.assertIn(">Questions<", nav)
        self.assertNotIn(">FAQ<", nav)
        self.assertIn('<h2 class="lp-title">Questions</h2>', self.client.get("/").content.decode())

    def test_login_page_says_log_in_in_tab_title_and_button(self):
        html = self.client.get("/auth/login").content.decode()
        self.assertIn("<title>Log in · MyBudget</title>", html)
        self.assertNotIn("Login <span", html)
        self.assertIn("Log in <span", html)

    def test_each_menu_label_matches_the_title_of_its_page(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345", first_name="Sam")
        self.client.force_login(user)
        cases = {"recurring_transactions": "Recurring transactions", "compare": "Yearly overview",
                 "activity_log": "Change history"}
        from django.urls import reverse
        home = self.client.get(reverse("dashboard")).content.decode()
        subnav = home.split('<nav class="subnav">')[1].split("</nav>")[0]
        for name, label in cases.items():
            self.assertIn(f">{label}</a>", subnav, label)
            page = self.client.get(reverse(name)).content.decode()
            self.assertIn(f"<h1", page)
            self.assertIn(f">{label}</h1>", page, f"H1 of {name}")
            self.assertIn(f"<title>{label} · MyBudget</title>", page, f"title of {name}")
        profile = self.client.get(reverse("accounts:profile", args=["sam"])).content.decode()
        self.assertIn(">Profile</h1>", profile)
        self.assertIn("<title>Profile · MyBudget</title>", profile)
        self.assertNotIn("My Profile", profile)
        self.assertNotIn("Settings ·", profile)
        self.assertIn("← Dashboard", profile)
        for old in (">Recurring</a>", ">Compare</a>", ">Activity</a>"):
            self.assertNotIn(old, subnav)

    def test_navbar_shows_the_first_name_or_profile_never_a_technical_username(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        named = U.objects.create_user(username="sam.t", email="sam.t@example.com", password="pass12345", first_name="Sam")
        self.client.force_login(named)
        self.assertIn('<span class="nav__user">Sam</span>', self.client.get("/app/").content.decode())
        bare = U.objects.create_user(username="copy.empty", email="copy.empty@example.com", password="pass12345")
        self.client.force_login(bare)
        html = self.client.get("/app/").content.decode()
        self.assertIn('<span class="nav__user">Profile</span>', html)
        self.assertNotIn(">copy.empty<", html.split('<main')[0])

    def test_footer_has_no_filler_and_explains_what_andreea_tech_is(self):
        footer = self.client.get("/").content.decode().split('class="container site-footer"')[1]
        self.assertNotIn("personal budget tracker", footer)
        self.assertIn("websites and web apps", footer)
        for label in ("About", "What's new", "Contact", "Privacy"):
            self.assertIn(f">{label}</a>", footer)

    def test_every_in_text_link_to_privacy_uses_the_same_label(self):
        import re
        for url in ("/", "/auth/register", "/contact"):
            html = self.client.get(url).content.decode()
            body = html.split("<main")[1].split("</main>")[0]
            labels = [re.sub(r"\s+", " ", m).strip() for m in re.findall(r'<a [^>]*href="/privacy"[^>]*>([^<]+)</a>', body)]
            for label in labels:
                self.assertIn(label, ("How your data is handled", "How your data is handled →"), f"{url}: {label!r}")
            self.assertTrue(labels, url)
        self.assertIn("<h1", self.client.get("/privacy").content.decode())
