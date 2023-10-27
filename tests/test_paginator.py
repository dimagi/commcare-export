import unittest

from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_minilinq import (
    DEFAULT_UCR_PAGE_SIZE,
    PaginationMode,
    get_paginator,
)


class PaginatorTest(unittest.TestCase):
    def test_ucr_paginator_page_size(self):
        checkpoint_manager = CheckpointManagerWithDetails(
            None, None, PaginationMode.cursor
        )
        paginator = get_paginator(
            resource="ucr",
            pagination_mode=checkpoint_manager.pagination_mode)
        paginator.init()
        initial_params = paginator.next_page_params_since(
            checkpoint_manager.since_param
        )
        self.assertEqual(initial_params["limit"], DEFAULT_UCR_PAGE_SIZE)

        paginator = get_paginator(
            resource="ucr",
            page_size=1,
            pagination_mode=checkpoint_manager.pagination_mode)
        paginator.init()
        initial_params = paginator.next_page_params_since(
            checkpoint_manager.since_param
        )
        self.assertEqual(initial_params["limit"], 1)