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
        self.assertContains(response, "How MyBudget handles your data")
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
        for anchor in ('id="screenshots"', 'id="how-it-works"', 'id="your-data"', 'id="faq"'):
            self.assertIn(anchor, self.html)

    def test_screenshots_are_real_files_with_alt_text_and_dimensions(self):
        import re
        from django.contrib.staticfiles import finders
        imgs = re.findall(r"<img[^>]+>", self.html)
        shots = [i for i in imgs if "shots/" in i]
        self.assertEqual(len(shots), 3)
        for tag in shots:
            self.assertRegex(tag, r'alt="[^"]{20,}"')
            self.assertIn("width=", tag)
            self.assertIn("height=", tag)
            self.assertIn('loading="lazy"', tag)
        for name in ("dashboard", "budgets", "goals"):
            self.assertIsNotNone(finders.find(f"img/shots/{name}.jpg"))

    def test_how_it_works_has_three_steps(self):
        self.assertEqual(self.html.count('class="glass-card step"'), 3)

    def test_faq_answers_match_what_the_app_does(self):
        self.assertEqual(self.html.count('class="glass-card faq__item"'), 8)
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
