import urllib
from odoo import http, fields, SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import AccessDenied
from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect
import base64
import logging  
_logger = logging.getLogger(__name__)


class RedirectPortalEntry(http.Controller):

    @http.route('/portal-entry', type='http', auth='user', website=True)
    def portal1(self, **kwargs):
        user = request.env.user
        if user.id == SUPERUSER_ID:
            request.session.logout(keep_db=True)
            return request.redirect('/web/login')
        if request.env.user.id == request.website.user_id.id:
            return request.redirect('/web/login?redirect=/my/home')
        # 👇 Redirektuj direktno na /portal koji koristi `website_dokumenti` template
        return request.redirect('/portal')


class TaskPortal(http.Controller):

    @http.route(['/my1/tasks'], type='http', auth='user', website=True)
    def list_tasks(self, **kwargs):
        user = request.env.user

        if not (user.has_group('base.group_portal') or user.has_group('base.group_system') or user.has_group('base.group_user')):
            raise AccessDenied()

        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])
        all_tasks = request.env['project.task'].sudo().search([('stage_id.fold', '=', False)])
        available_tasks = all_tasks.filtered(lambda t: not t.offer_ids.filtered(lambda o: o.team_id.id in teams.ids))

        return request.render('odoo_projekat_vjezba.portal_my_tasks_template', {
            'tasks': available_tasks,
        })


class PortalOffer(http.Controller):

    @http.route(['/portal1/my_offers'], type='http', auth='user', website=True)
    def my_offers(self, **kwargs):
        user = request.env.user

        if not (user.has_group('base.group_portal') or user.has_group('base.group_system') or user.has_group('base.group_user')):
            raise AccessDenied()

        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])
        offers = request.env['task.offer'].search([('team_id', 'in', teams.ids)])

        # ✅ koristi bolji snippet view
        return request.render('odoo_projekat_vjezba.portal_my_offers_content', {
            'offers': offers,
        })


    @http.route(['/portal1/offer/approval/<int:approval_id>'], type='http', auth='user', website=True)
    def offer_approval_form(self, approval_id, **post):
        user = request.env.user
        if not (user.has_group('base.group_portal') or user.has_group('base.group_system') or user.has_group('base.group_user')):
            raise AccessDenied()

        approval = request.env['offer.approval'].sudo().browse(approval_id)
        if not approval.exists():
            return request.not_found()

        if approval.approver_id.id != user.id:
            raise AccessDenied()

        error = None
        if post and request.httprequest.method == 'POST':
            action = post.get('action')
            note = post.get('note', '')
            if action == 'approve':
                approval.sudo().write({'state': 'approved', 'note': note})
            elif action == 'reject':
                approval.sudo().write({'state': 'rejected', 'note': note})
            return request.redirect('/portal1/my_offers')

        return request.render('odoo_projekat_vjezba.portal_offer_approval_form', {
            'approval': approval,
            'error': error,
        })


class TaskDocumentPortal(http.Controller):

    @http.route(['/portal1/offer/<int:offer_id>/documents'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def offer_documents(self, offer_id, **post):
        user = request.env.user

        if not (user.has_group('base.group_portal') or user.has_group('base.group_system') or user.has_group('base.group_user')):
            raise AccessDenied()

        offer = request.env['task.offer'].sudo().browse(offer_id)
        if not offer.exists():
            raise NotFound()

        team = offer.team_id
        task = offer.task_id

        if team.leader_id.id != user.id or offer.status != 'accepted':
            raise AccessDenied("Nemate pristup ovoj ponudi.")

        error = None

        if post and request.httprequest.method == 'POST':
            file = request.httprequest.files.get('file')
            if file:
                try:
                    file_data = file.read()
                    file_name = file.filename
                    file_type = file.mimetype

                    request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'datas': base64.b64encode(file_data),
                        'res_model': 'task.offer',
                        'res_id': offer.id,
                        'mimetype': file_type,
                        'type': 'binary',
                    })

                    contract = request.env['task.contract'].sudo().search([('offer_id', '=', offer.id)], limit=1)

                    if contract:
                        contract.write({
                            'user_signed_agreement': base64.b64encode(file_data),
                            'user_signed_agreement_filename': file_name,
                            'is_signed': True,
                            'date_signed': fields.Date.today(),
                            'status': 'uploaded',
                        })

                except Exception as e:
                    error = f"Greška pri uploadu: {str(e)}"

        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'task.offer'),
            ('res_id', '=', offer.id)
        ])

        return request.render('odoo_projekat_vjezba.portal_task_documents', {
            'offer': offer,
            'task': task,
            'attachments': attachments,
            'error': error,
        })


class TaskContractPortal(http.Controller):

    @http.route(['/portal1/my_contracts'], type='http', auth='user', website=True)
    def list_contracts(self, **kwargs):
        user = request.env.user

        if not (user.has_group('base.group_portal') or user.has_group('base.group_system') or user.has_group('base.group_user')):
            raise AccessDenied()

        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])
        accepted_offers = request.env['task.offer'].search([
            ('team_id', 'in', teams.ids),
            ('status', '=', 'accepted')
        ])
        task_ids = accepted_offers.mapped('task_id').ids

        contracts = request.env['task.contract'].search([
            ('task_id', 'in', task_ids),
            ('team_id', 'in', teams.ids)
        ])

        # ✅ koristi snippet view
        return request.render('odoo_projekat_vjezba.portal_my_contracts_content', {
            'contracts': contracts,
        })


class PortalProjects(http.Controller):

    @http.route('/my1/projects', type='http', auth='user', website=True)
    def portal_my_projects(self, **kwargs):
        partner = request.env.user.partner_id
        projects = request.env['project.project'].sudo().search([
            ('partner_id', '=', partner.id)
        ])

        contractor_map = {p.id: p.partner_id.id == partner.id for p in projects}

        return request.render('odoo_projekat_vjezba.portal_my_projects_content', {
            'projects': projects,
            'contractor_map': contractor_map,
            'show_mine': False,
            'show_access_denied_modal': False,
        })

    # ⬇⬇⬇ DODAJ OVO NOVO:
    @http.route('/portal/projects/snippet', type='http', auth='user', website=True)
    def portal_projects_snippet(self, **kwargs):
        partner = request.env.user.partner_id
        show_mine = kwargs.get('show_mine') == 'true'

        if show_mine:
            projects = request.env['project.project'].sudo().search([
                ('partner_id', '=', partner.id)
            ])
        else:
            projects = request.env['project.project'].sudo().search([])

        contractor_map = {p.id: p.partner_id.id == partner.id for p in projects}

        return request.render('odoo_projekat_vjezba.portal_my_projects_content', {
            'projects': projects,
            'contractor_map': contractor_map,
            'show_mine': show_mine,
            'show_access_denied_modal': False,
        })




class ContractPortal(http.Controller):

    @http.route(['/portal1/task/<int:task_id>/contract'], type='http', auth='user', website=True)
    def view_contract(self, task_id, **kwargs):
        user = request.env.user

        task = request.env['project.task'].sudo().browse(task_id)
        if not task.exists():
            raise NotFound()

        contract = request.env['task.contract'].sudo().search([
            ('task_id', '=', task.id),
            ('team_id.leader_id', '=', user.id)
        ], limit=1)

        if not contract:
            raise AccessDenied()

        return request.render('odoo_projekat_vjezba.portal_contract_detail_template', {
            'contract': contract
        })
