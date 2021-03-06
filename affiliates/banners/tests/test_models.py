from django.core.exceptions import ValidationError
from django.test.utils import override_settings

from nose.tools import eq_, ok_
from mock import Mock, patch

from affiliates.banners.models import Banner, ImageVariation
from affiliates.banners.tests import (CategoryFactory, FirefoxUpgradeBannerVariationFactory,
                                      ImageBannerFactory, ImageBannerVariationFactory,
                                      TextBannerFactory, TextBannerVariationFactory)
from affiliates.base.tests import TestCase
from affiliates.links.models import Link
from affiliates.users.tests import UserFactory


class CategoryTests(TestCase):
    def test_category_clean(self):
        """
        If a category is more than one layer away from its root, clean
        should raise a ValidationError.
        """
        root = CategoryFactory.create()
        child = CategoryFactory.create(parent=root)
        grandchild = CategoryFactory.create(parent=child)

        root.clean()  # No layers is fine!
        child.clean()  # 1 layer is fine!
        with self.assertRaises(ValidationError):
            grandchild.clean()  # 2 layers is no bueno!


class BannerTests(TestCase):
    def test_create_link(self):
        """
        create_link should create a Link object using this banner's
        description and generated code.
        """
        banner = Banner(destination='https://www.mozilla.org')
        banner.generate_banner_code = Mock(return_value="""
            <a href="{href}">Link!</a>
        """)
        banner.get_banner_type = Mock(return_value='generic_banner')
        user = UserFactory.create()
        variation = TextBannerVariationFactory.create()

        with patch.object(Link, 'get_referral_url') as get_referral_url:
            get_referral_url.return_value = 'asdf'
            link = banner.create_link(user, variation)

        ok_(isinstance(link, Link))
        eq_(link.user, user)
        eq_(link.banner_variation, variation)
        self.assertHTMLEqual(link.html, """
            <a href="asdf">Link!</a>
        """)
        banner.generate_banner_code.assert_called_with(variation)


@override_settings(MEDIA_URL='/media/')
class ImageBannerBaseTests(TestCase):
    # Test base behavior via ImageBanner because mocking would be
    # tedious and wouldn't help prove much.

    def setUp(self):
        self.banner = ImageBannerFactory.create()
        self.banner.preview_template = 'test_template.html'

        patcher = patch('affiliates.banners.models.render_to_string')
        self.addCleanup(patcher.stop)
        self.render_to_string = patcher.start()
        self.render_to_string.return_value = 'asdf'

        patcher = patch('affiliates.banners.models.translation.get_language')
        self.addCleanup(patcher.stop)
        self.get_language = patcher.start()

    def test_preview_html_localized_variations(self):
        """
        If 125x125 variations in the correct locale are available, use
        the first one as the preview image.
        """
        ImageBannerVariationFactory.create(banner=self.banner, width=125, height=125, locale='fr',
                                           image='uploads/banners/test.png')

        self.get_language.return_value = 'fr'
        eq_(self.banner.preview_html('http://example.com', foo='bar'), 'asdf')
        self.render_to_string.assert_called_with('test_template.html', {
            'href': 'http://example.com',
            'foo': 'bar',
            'banner': self.banner,
            'preview_img': '/media/uploads/banners/test.png',
        })

    def test_preview_html_fallback(self):
        """
        If there are no previews available in the current locale, but
        are available in en-US, use them.
        """
        ImageBannerVariationFactory.create(banner=self.banner, width=125, height=125,
                                           locale='en-us', image='uploads/banners/test.png')
        ImageBannerVariationFactory.create(banner=self.banner, width=300, height=125,
                                           locale='fr', image='uploads/banners/test.png')

        self.get_language.return_value = 'fr'
        eq_(self.banner.preview_html('http://example.com', foo='bar'), 'asdf')
        self.render_to_string.assert_called_with('test_template.html', {
            'href': 'http://example.com',
            'foo': 'bar',
            'banner': self.banner,
            'preview_img': '/media/uploads/banners/test.png',
        })

    def test_preview_html_none(self):
        """
        If no variations are available at the right size and locale, and
        no fallbacks are available either, don't include a preview_img.
        """
        ImageBannerVariationFactory.create(banner=self.banner, width=125, height=125,
                                           locale='de', image='uploads/banners/test.png')
        ImageBannerVariationFactory.create(banner=self.banner, width=300, height=125,
                                           locale='fr', image='uploads/banners/test.png')

        self.get_language.return_value = 'fr'
        eq_(self.banner.preview_html('http://example.com', foo='bar'), 'asdf')
        self.render_to_string.assert_called_with('test_template.html', {
            'href': 'http://example.com',
            'foo': 'bar',
            'banner': self.banner,
        })


class ImageBannerTests(TestCase):
    def test_generate_banner_code(self):
        # This is less a test of initial correctness and more to alert
        # us of unexpected changes to banner code generation.
        variation = ImageBannerVariationFactory(banner__destination='https://www.mozilla.org',
                                                image='uploads/banners/test.png')
        banner = variation.banner

        with self.settings(MEDIA_URL='/media/', SITE_URL='https://example.com'):
            self.assertHTMLEqual(banner.generate_banner_code(variation), """
              <a href="{href}">
                <img src="https://example.com/media/uploads/banners/test.png" alt="">
              </a>
            """)


class ImageVariationTests(TestCase):
    def test_size(self):
        variation = ImageVariation()
        variation.image = Mock(width=250, height=140)
        eq_(variation.size, '250 &times; 140')

    def test_filename(self):
        variation = ImageVariation(color='blue', locale='en-us')
        variation.banner_id = 7
        variation.image = Mock(width=250, height=140)
        variation.get_media_subdirectory = Mock(return_value='uploads/test')

        with patch('affiliates.banners.models.hashlib.sha1') as sha1:
            sha1.return_value.hexdigest.return_value = 'somehash'
            filename = variation._filename('test_file.png')

        # Filename should take the path from get_media_subdirectory and
        # the hash from sha1.hexdigest, which should've been given a
        # string with data unique to this variation.
        eq_(filename, 'uploads/test/somehash.png')
        sha1.assert_called_with('7_250_140_blue_en-us')


class TextBannerTests(TestCase):
    def test_generate_banner_code(self):
        banner = TextBannerFactory()
        variation = TextBannerVariationFactory(text='Test')
        eq_(banner.generate_banner_code(variation=variation), '<a href="{href}">Test</a>')


class FirefoxUpgradeBannerTests(TestCase):
    def test_generate_banner_code(self):
        # This is less a test of initial correctness and more to alert
        # us of unexpected changes to banner code generation.
        variation = FirefoxUpgradeBannerVariationFactory.create(
            banner__destination='https://www.mozilla.org',
            image='uploads/firefox_upgrade_banners/test.png',
            upgrade_image='uploads/firefox_upgrade_banners/test_upgrade.png')
        banner = variation.banner

        with self.settings(MEDIA_URL='/media/', SITE_URL='https://example.com'):
            self.assertHTMLEqual(banner.generate_banner_code(variation), """
              <a href="{{href}}">
                <img src="https://example.com/media/uploads/upgrade/{pk}">
              </a>
            """.format(pk=variation.pk))
