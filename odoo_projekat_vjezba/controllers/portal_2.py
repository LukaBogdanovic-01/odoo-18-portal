import urllib
from odoo import http, fields, SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import AccessDenied
from werkzeug.utils import redirect # type: ignore
from werkzeug.exceptions import NotFound # type: ignore
import base64
import logging  
_logger = logging.getLogger(__name__)



class CustomPortalHome(http.Controller):

    @http.route('/portal2-entry', auth='user', website=True)
    def portal2(self, **kwargs):
        user = request.env.user
        if user.id == SUPERUSER_ID:
            request.session.logout(keep_db=True)  # izloguj superusera
            return request.redirect('/web/login')
        if request.env.user.id == request.website.user_id.id:
            return request.redirect('/web/login?redirect=/my2/home')
        return request.render('odoo_projekat_vjezba.portal2_my_home', {})




class TaskPortal2(http.Controller):

    @http.route(['/my2/tasks'], type='http', auth='user', website=True)
    def list_tasks_2(self, **kwargs):
        user = request.env.user

        # Provjera da li je portal korisnik
        if not user.has_group('base.group_portal'):
            raise AccessDenied()

        # Nađemo timove gde je korisnik lider
        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])

        # Dohvati sve zadatke koji NISU završeni
        all_tasks = request.env['project.task'].sudo().search([('stage_id.fold', '=', False)])

        # Filtriraj zadatke na koje nijedan tim korisnika još nije poslao ponudu
        available_tasks = all_tasks.filtered(lambda t: not t.offer_ids.filtered(lambda o: o.team_id.id in teams.ids))

        values = {
            'tasks': available_tasks,
        }
        return request.render('odoo_projekat_vjezba.portal2_my_tasks_template', values)



class PortalOffer2(http.Controller):

    # @http.route(['/portal/offer/create'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    # def offer_create(self, **post):
    #     user = request.env.user

    #     if not user.has_group('base.group_portal'):
    #         raise AccessDenied()

    #     tasks = request.env['project.task'].search([])
    #     teams = request.env['construction.team'].search([('leader_id', '=', user.id)])
    #     all_tasks = request.env['project.task'].sudo().search([('stage_id.fold', '=', False)])
    #     available_tasks = all_tasks.filtered(lambda t: not t.offer_ids.filtered(lambda o: o.team_id.id in teams.ids))


    #     error = None

    #     if post and request.httprequest.method == 'POST':
    #         task_id = post.get('task_id')
    #         team_id = post.get('team_id')
    #         price = post.get('price')
    #         deadline = post.get('deadline')

    #         if not task_id or not team_id or not price or not deadline:
    #             error = "Sva polja su obavezna."
    #         else:
    #             try:
    #                 vals = {
    #                     'task_id': int(task_id),
    #                     'team_id': int(team_id),
    #                     'price': float(price),
    #                     'deadline': deadline,
    #                     'status': 'draft',
    #                 }
    #                 offer = request.env['task.offer'].sudo().create(vals)

    #                 # Kreiraj approval odmah
    #                 request.env['offer.approval'].sudo().create({
    #                     'offer_id': offer.id,
    #                     'approver_id': request.env.uid,  # Možeš promijeniti na default menadžera ako želiš
    #                 })

    #                 return request.redirect('/portal/my_offers')

    #             except Exception as e:
    #                 error = f"Greška pri snimanju: {str(e)}"

    #     return request.render('odoo_projekat_vjezba.portal_offer_form_new', {
    #         'tasks': available_tasks,
    #         'teams': teams,
    #         'error': error,
    #     })


    @http.route(['/portal2/my_offers'], type='http', auth='user', website=True)
    def my_offers_2(self, **kwargs):
        user = request.env.user

        # Provjera da li je portal korisnik
        if not user.has_group('base.group_portal'):
            raise AccessDenied()

        # Timski lider
        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])

        offers = request.env['task.offer'].search([
            ('team_id', 'in', teams.ids)
        ])

        return request.render('odoo_projekat_vjezba.portal2_my_offers_template', {
            'offers': offers,
        })


    @http.route(['/portal2/offer/approval/<int:approval_id>'], type='http', auth='user', website=True)
    def offer_approval_form_2(self, approval_id, **post):
        user = request.env.user
        if not user.has_group('base.group_portal'):
            raise AccessDenied()

        approval = request.env['offer.approval'].sudo().browse(approval_id)
        if not approval.exists():
            return request.not_found()

        # Proveri da li korisnik može da vidi ovu ponudu/odobrenje (npr. ako je lider tima)
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
            return request.redirect('/portal2/my_offers')

        return request.render('odoo_projekat_vjezba.portal2_offer_approval_form', {
            'approval': approval,
            'error': error,
        })



class TaskDocumentPortal2(http.Controller):

    @http.route(['/portal2/offer/<int:offer_id>/documents'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def offer_documents_2(self, offer_id, **post):
        user = request.env.user

        if not user.has_group('base.group_portal'):
            raise AccessDenied()

        offer = request.env['task.offer'].sudo().browse(offer_id)
        if not offer.exists():
            raise NotFound()

        team = offer.team_id
        task = offer.task_id

        # Provera da li je korisnik lider tima i da li je ponuda prihvaćena
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

                    # 1. Kreiraj attachment za ponudu (task.offer)
                    request.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'datas': base64.b64encode(file_data),
                        'res_model': 'task.offer',
                        'res_id': offer.id,
                        'mimetype': file_type,
                        'type': 'binary',
                    })

                    # 2. Pronađi ugovor vezan za ponudu
                    contract = request.env['task.contract'].sudo().search([('offer_id', '=', offer.id)], limit=1)

                    if contract:
                        # 3. Popuni polja na ugovoru
                        contract.write({
                            'user_signed_agreement': base64.b64encode(file_data),
                            'user_signed_agreement_filename': file_name,
                            'is_signed': True,
                            'date_signed': fields.Date.today(),
                            'status': 'uploaded',
                        })

                except Exception as e:
                    error = f"Greška pri uploadu: {str(e)}"

        # Dohvati sve attachmente vezane za ovu ponudu
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'task.offer'),
            ('res_id', '=', offer.id)
        ])

        return request.render('odoo_projekat_vjezba.portal2_task_documents', {
            'offer': offer,
            'task': task,
            'attachments': attachments,
            'error': error,
        })




class TaskContractPortal2(http.Controller):

    @http.route(['/portal2/my_contracts'], type='http', auth='user', website=True)
    def list_contracts_2(self, **kwargs):
        user = request.env.user

        if not user.has_group('base.group_portal'):
            raise AccessDenied()

        teams = request.env['construction.team'].search([('leader_id', '=', user.id)])
        # Pronađi prihvaćene ponude tima korisnika
        accepted_offers = request.env['task.offer'].search([
            ('team_id', 'in', teams.ids),
            ('status', '=', 'accepted')
        ])
        task_ids = accepted_offers.mapped('task_id').ids

        contracts = request.env['task.contract'].search([
            ('task_id', 'in', task_ids),
            ('team_id', 'in', teams.ids)
        ])

        return request.render('odoo_projekat_vjezba.portal2_my_contracts_template', {
            'contracts': contracts,
        })

class PortalProjects2(http.Controller):

    @http.route('/my2/projects', type='http', auth='user', website=True)
    def portal_my_projects_2(self, **kwargs):
        partner = request.env.user.partner_id
        projects = request.env['project.project'].sudo().search([
            ('partner_id', '=', partner.id)
        ])
        return request.render('odoo_projekat_vjezba.portal2_my_projects_template', {
            'projects': projects
        })

class ContractPortal2(http.Controller):

    @http.route(['/portal2/task/<int:task_id>/contract'], type='http', auth='user', website=True)
    def view_contract_2(self, task_id, **kwargs):
        user = request.env.user

        task = request.env['project.task'].sudo().browse(task_id)
        if not task.exists():
            raise NotFound()

        # Pronađi ugovor povezan sa ovim taskom koji pripada korisnikovom timu
        contract = request.env['task.contract'].sudo().search([
            ('task_id', '=', task.id),
            ('team_id.leader_id', '=', user.id)
        ], limit=1)

        if not contract:
            raise AccessDenied()

        return request.render('odoo_projekat_vjezba.portal2_contract_detail_template', {
            'contract': contract
        })