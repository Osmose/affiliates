from datetime import date

from django.test.client import RequestFactory

from mock import ANY, call, Mock, patch
from nose.tools import eq_

from affiliates.base.tests import CONTAINS, TestCase
from affiliates.links.admin import FraudActionAdmin
from affiliates.links.models import FraudAction
from affiliates.links.tests import FraudActionFactory


class FraudActionAdminTests(TestCase):
    def setUp(self):
        self.model_admin = FraudActionAdmin(FraudAction, Mock())
        self.factory = RequestFactory()

    def test_reverse_actions(self):
        """
        reverse_actions should call reverse on each action in the given
        queryset. If an action raises a RuntimeError, message the user
        and move on.
        """
        action1, action2 = FraudActionFactory.create_batch(2, datapoint__date=date(2014, 1, 1))

        def side(self):
            if self == action2:
                raise RuntimeError('something something')

        request = self.factory.post('/')
        queryset = FraudAction.objects.order_by('id')

        self.model_admin.message_user = Mock()
        with patch.object(FraudAction, 'reverse', autospec=True, side_effect=side) as reverse:
            self.model_admin.reverse_actions(request, queryset)
            eq_(reverse.call_args_list, [call(action1), call(action2)])

        expected_calls = [
            call(request, CONTAINS(unicode(action2.id)), 'error'),
            call(request, ANY, 'info'),
        ]
        eq_(self.model_admin.message_user.call_args_list, expected_calls)
