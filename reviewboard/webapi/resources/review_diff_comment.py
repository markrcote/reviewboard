from django.core.exceptions import ObjectDoesNotExist
from djblets.util.decorators import augment_method_from
from djblets.webapi.decorators import (webapi_login_required,
                                       webapi_response_errors,
                                       webapi_request_fields)
from djblets.webapi.errors import (DOES_NOT_EXIST, INVALID_FORM_DATA,
                                   NOT_LOGGED_IN, PERMISSION_DENIED)

from reviewboard.diffviewer.models import FileDiff
from reviewboard.reviews.models import BaseComment
from reviewboard.webapi.decorators import webapi_check_local_site
from reviewboard.webapi.resources import resources
from reviewboard.webapi.resources.base_diff_comment import \
    BaseDiffCommentResource


class ReviewDiffCommentResource(BaseDiffCommentResource):
    """Provides information on diff comments made on a review.

    If the review is a draft, then comments can be added, deleted, or
    changed on this list. However, if the review is already published,
    then no changes can be made.
    """
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    model_parent_key = 'review'

    mimetype_list_resource_name = 'review-diff-comments'
    mimetype_item_resource_name = 'review-diff-comment'

    def get_queryset(self, request, review_request_id, review_id,
                     *args, **kwargs):
        q = super(ReviewDiffCommentResource, self).get_queryset(
            request, review_request_id, *args, **kwargs)
        return q.filter(review=review_id)

    @webapi_check_local_site
    @webapi_login_required
    @webapi_response_errors(DOES_NOT_EXIST, INVALID_FORM_DATA,
                            NOT_LOGGED_IN, PERMISSION_DENIED)
    @webapi_request_fields(
        required={
            'filediff_id': {
                'type': int,
                'description': 'The ID of the file diff the comment is on.',
            },
            'first_line': {
                'type': int,
                'description': 'The line number the comment starts at.',
            },
            'num_lines': {
                'type': int,
                'description': 'The number of lines the comment spans.',
            },
            'text': {
                'type': str,
                'description': 'The comment text.',
            },
        },
        optional={
            'interfilediff_id': {
                'type': int,
                'description': 'The ID of the second file diff in the '
                               'interdiff the comment is on.',
            },
            'issue_opened': {
                'type': bool,
                'description': 'Whether the comment opens an issue.',
            },
        },
        allow_unknown=True,
    )
    def create(self, request, first_line, num_lines, text,
               filediff_id, issue_opened=False, interfilediff_id=None,
               extra_fields={}, *args, **kwargs):
        """Creates a new diff comment.

        This will create a new diff comment on this review. The review
        must be a draft review.
        """
        try:
            review_request = \
                resources.review_request.get_object(request, *args, **kwargs)
            review = resources.review.get_object(request, *args, **kwargs)
        except ObjectDoesNotExist:
            return DOES_NOT_EXIST

        if not resources.review.has_modify_permissions(request, review):
            return self._no_access_error(request.user)

        filediff = None
        interfilediff = None
        invalid_fields = {}

        try:
            filediff = FileDiff.objects.get(
                pk=filediff_id,
                diffset__history__review_request=review_request)
        except ObjectDoesNotExist:
            invalid_fields['filediff_id'] = \
                ['This is not a valid filediff ID']

        if filediff and interfilediff_id:
            if interfilediff_id == filediff.id:
                invalid_fields['interfilediff_id'] = \
                    ['This cannot be the same as filediff_id']
            else:
                try:
                    interfilediff = FileDiff.objects.get(
                        pk=interfilediff_id,
                        diffset__history=filediff.diffset.history)
                except ObjectDoesNotExist:
                    invalid_fields['interfilediff_id'] = \
                        ['This is not a valid interfilediff ID']

        if invalid_fields:
            return INVALID_FORM_DATA, {
                'fields': invalid_fields,
            }

        new_comment = self.model(filediff=filediff,
                                 interfilediff=interfilediff,
                                 text=text.strip(),
                                 first_line=first_line,
                                 num_lines=num_lines,
                                 issue_opened=bool(issue_opened))

        self._import_extra_data(new_comment.extra_data, extra_fields)

        if issue_opened:
            new_comment.issue_status = BaseComment.OPEN
        else:
            new_comment.issue_status = None

        new_comment.save()

        review.comments.add(new_comment)
        review.save()

        return 201, {
            self.item_result_key: new_comment,
        }

    @webapi_check_local_site
    @webapi_login_required
    @webapi_response_errors(DOES_NOT_EXIST, NOT_LOGGED_IN, PERMISSION_DENIED)
    @webapi_request_fields(
        optional={
            'first_line': {
                'type': int,
                'description': 'The line number the comment starts at.',
            },
            'num_lines': {
                'type': int,
                'description': 'The number of lines the comment spans.',
            },
            'text': {
                'type': str,
                'description': 'The comment text.',
            },
            'issue_opened': {
                'type': bool,
                'description': 'Whether or not the comment opens an issue.',
            },
            'issue_status': {
                'type': ('dropped', 'open', 'resolved'),
                'description': 'The status of an open issue.',
            }
        },
        allow_unknown=True,
    )
    def update(self, request, extra_fields={}, *args, **kwargs):
        """Updates a diff comment.

        This can update the text or line range of an existing comment.
        """
        try:
            resources.review_request.get_object(request, *args, **kwargs)
            review = resources.review.get_object(request, *args, **kwargs)
            diff_comment = self.get_object(request, *args, **kwargs)
        except ObjectDoesNotExist:
            return DOES_NOT_EXIST

        # Determine whether or not we're updating the issue status.
        if self.should_update_issue_status(diff_comment, **kwargs):
            return self.update_issue_status(request, self, *args, **kwargs)

        if not resources.review.has_modify_permissions(request, review):
            return self._no_access_error(request.user)

        # If we've updated the comment from having no issue opened,
        # to having an issue opened, we need to set the issue status
        # to OPEN.
        if not diff_comment.issue_opened and kwargs.get('issue_opened', False):
            diff_comment.issue_status = BaseComment.OPEN

        # If we've updated the comment from having an issue opened to having
        # no issue opened, set the issue status back to null.
        if diff_comment.issue_opened and not kwargs.get('issue_opened', True):
            diff_comment.issue_status = None

        for field in ('text', 'first_line', 'num_lines', 'issue_opened'):
            value = kwargs.get(field, None)

            if value is not None:
                setattr(diff_comment, field, value)

        self._import_extra_data(diff_comment.extra_data, extra_fields)
        diff_comment.save()

        return 200, {
            self.item_result_key: diff_comment,
        }

    @webapi_check_local_site
    @augment_method_from(BaseDiffCommentResource)
    def delete(self, *args, **kwargs):
        """Deletes the comment.

        This will remove the comment from the review. This cannot be undone.

        Only comments on draft reviews can be deleted. Attempting to delete
        a published comment will return a Permission Denied error.

        Instead of a payload response, this will return :http:`204`.
        """
        pass

    @webapi_check_local_site
    @augment_method_from(BaseDiffCommentResource)
    def get_list(self, *args, **kwargs):
        """Returns the list of comments made on a review.

        This list can be filtered down by using the ``?line=`` and
        ``?interdiff-revision=``.

        To filter for comments that start on a particular line in the file,
        using ``?line=``.

        To filter for comments that span revisions of diffs, you can specify
        the second revision in the range using ``?interdiff-revision=``.
        """
        pass


review_diff_comment_resource = ReviewDiffCommentResource()
