from odoo import http
from odoo.http import request

class DokumentaTabPortal(http.Controller):

    @http.route('/portal/info/snippet', type='http', auth='user', website=True)
    def portal_info_tabla_snippet(self, **kwargs):
        current_user = request.env.user

        notifications = request.env['info.notification'].sudo().search([], order="create_date desc")
        messages = request.env['info.chat.message'].sudo().search([
            ('receiver_id', '=', current_user.id)
        ], order="create_date desc", limit=20)
        users = request.env['res.users'].sudo().search([])

        return request.render('odoo_projekat_vjezba.portal_info_tabla_content', {
            'notifications': notifications,
            'messages': messages,
            'users': users,
        })

           
    @http.route('/portal/info/comment/<int:notification_id>', type='http', auth='user', website=True, methods=['POST'])
    def post_notification_comment(self, notification_id, **post):
        body = post.get('body')
        if body:
            request.env['info.notification.comment'].sudo().create({
                'body': body,
                'notification_id': notification_id,
                'author_id': request.env.user.id,
            })
        return request.redirect('/portal/info/snippet')

    @http.route('/portal/info/chat', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_info_chat(self, **post):
        current_user = request.env.user

        receiver_raw = post.get('receiver_id') or request.httprequest.args.get('receiver_id')
        receiver_id = int(receiver_raw) if receiver_raw and receiver_raw.isdigit() else None
        show_mine = request.params.get('show_mine') == 'true'


        # Ako korisnik šalje poruku
        if request.httprequest.method == 'POST':
            message = post.get('body')
            if receiver_id and message:
                request.env['info.chat.message'].sudo().create({
                    'body': message,
                    'receiver_id': receiver_id,
                    'sender_id': current_user.id,
                })
                return request.redirect(f'/portal/info/chat?receiver_id={receiver_id}')

        # 📥 Info tabla
        notifications = request.env['info.notification'].sudo().search([], order="create_date desc")
        messages = request.env['info.chat.message'].sudo().search([
            '|',
            ('receiver_id', '=', current_user.id),
            ('sender_id', '=', current_user.id),
        ], order='create_date desc', limit=20)
        all_users = request.env['res.users'].sudo().search([])

        # 📦 Ugovori & ponude
        teams = request.env['construction.team'].sudo().search([('leader_id', '=', current_user.id)])
        offers = request.env['task.offer'].sudo().search([('team_id', 'in', teams.ids)]) if teams else request.env['task.offer'].browse([])
        contracts = request.env['task.contract'].sudo().search([('team_id', 'in', teams.ids)]) if teams else request.env['task.contract'].browse([])

        # 📁 Projekti
        partner = current_user.partner_id
        projects = request.env['project.project'].sudo().search([])
        contractor_map = {p.id: p.partner_id.id == partner.id for p in projects}

        return request.render('odoo_projekat_vjezba.website_dokumenti', {
            'notifications': notifications,
            'messages': messages,
            'users': all_users,
            'selected_user_id': receiver_id,
            'offers': offers,
            'contracts': contracts,
            'projects': projects,
            'contractor_map': contractor_map,
            'show_mine': False,
            'show_access_denied_modal': False,
            'show_mine': show_mine,
        })



    
    @http.route('/portal/info/create_notification', type='http', auth='user', website=True, methods=['POST'])
    def create_notification(self, **post):
        name = post.get('name')
        body = post.get('body')
        if name and body:
            request.env['info.notification'].sudo().create({
                'name': name,
                'body': body,
                'author_id': request.env.user.id,
            })
        return request.redirect('/portal/info/snippet')  # ili return '' za tihi odgovor





    @http.route('/portal/offers/snippet', type='http', auth='user', website=True)
    def portal_offers_snippet(self):
        # Korisnik koji je trenutno prijavljen
        current_user = request.env.user

        # Pronađi sve timove kojima je lider ovaj korisnik
        teams = request.env['construction.team'].sudo().search([
            ('leader_id', '=', current_user.id)
        ])

        # Ako korisnik nije lider ni jednog tima, nema ponuda
        if not teams:
            offers = request.env['task.offer'].browse([])
        else:
            offers = request.env['task.offer'].sudo().search([
                ('team_id', 'in', teams.ids)
            ])

        return request.render('odoo_projekat_vjezba.portal_my_offers_content', {
            'offers': offers,
        })

    @http.route('/portal/contracts/snippet', type='http', auth='user', website=True)
    def portal_contracts_snippet(self, **kwargs):
        # Trenutno prijavljeni korisnik
        current_user = request.env.user

        # Pronađi sve timove kojima je lider ovaj korisnik
        teams = request.env['construction.team'].sudo().search([
            ('leader_id', '=', current_user.id)
        ])

        # Ako korisnik nije lider nijednog tima, nema ugovora
        if not teams:
            contracts = request.env['task.contract'].browse([])
        else:
            contracts = request.env['task.contract'].sudo().search([
                ('team_id', 'in', teams.ids)
            ])

        return request.render('odoo_projekat_vjezba.portal_my_contracts_content', {
            'contracts': contracts,
        })


    @http.route('/portal/projects/snippet', type='http', auth='user', website=True)
    def portal_projects_snippet(self, show_mine=False, **kwargs):
        current_user = request.env.user
        partner = current_user.partner_id

        domain = []
        if show_mine:
            domain = [('partner_id', '=', partner.id)]

        projects = request.env['project.project'].sudo().search(domain)

        # Mapiranje ID na flag
        contractor_map = {p.id: p.partner_id.id == partner.id for p in projects}

        return request.render('odoo_projekat_vjezba.portal_my_projects_content', {
            'breadcrumbs': [
        {'name': 'Projekti', 'url': None},  # aktivna strana
    ],
            'projects': projects,
            'contractor_map': contractor_map,
            'show_mine': show_mine,
        })

    @http.route('/portal/project/tasks_kanban/<int:project_id>', type='http', auth='user', website=True)
    def project_tasks_kanban(self, project_id):
        project = request.env['project.project'].sudo().browse(project_id)
        tasks = project.task_ids
        return request.render('odoo_projekat_vjezba.portal_project_tasks_list', {
            'project': project,
            'tasks': tasks,
            'breadcrumbs': [
        {'name': 'Projekti', 'url': '/portal/projects/snippet'},
        {'name': project.name, 'url': None},
    ],
        })


    @http.route('/portal', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_main(self, **post):
        current_user = request.env.user

        # Ako korisnik šalje novo obavještenje
        if request.httprequest.method == 'POST':
            name = post.get('name')
            body = post.get('body')
            if name and body:
                request.env['info.notification'].sudo().create({
                    'name': name,
                    'body': body,
                    'author_id': current_user.id,
                })

        # Info tabla podaci
        notifications = request.env['info.notification'].sudo().search([], order="create_date desc")
        messages = request.env['info.chat.message'].sudo().search([
            '|',
            ('receiver_id', '=', current_user.id),
            ('sender_id', '=', current_user.id),
        ], order="create_date desc", limit=20)
        users = request.env['res.users'].sudo().search([])

        # Ponude i ugovori
        teams = request.env['construction.team'].sudo().search([('leader_id', '=', current_user.id)])
        offers = request.env['task.offer'].sudo().search([('team_id', 'in', teams.ids)]) if teams else request.env['task.offer'].browse([])
        contracts = request.env['task.contract'].sudo().search([('team_id', 'in', teams.ids)]) if teams else request.env['task.contract'].browse([])

        # Projekti (opciono odmah učitati sve, ili koristi AJAX)
        partner = current_user.partner_id
        projects = request.env['project.project'].sudo().search([])
        contractor_map = {p.id: p.partner_id.id == partner.id for p in projects}

        return request.render('odoo_projekat_vjezba.website_dokumenti', {
            'notifications': notifications,
            'messages': messages,
            'users': users,
            'offers': offers,
            'contracts': contracts,
            'projects': projects,
            'contractor_map': contractor_map,
            'show_mine': False,  # možeš dinamički kontrolisati kroz dugme
            'show_access_denied_modal': False,  # po potrebi
        })


    #Za brisanje obavjestenja 
    @http.route('/portal/info/delete_notification/<int:notification_id>', type='http', auth='user', website=True, methods=['POST'])
    def delete_notification(self, notification_id, **kwargs):
        note = request.env['info.notification'].sudo().browse(notification_id)
        if note.exists():
            note.unlink()
        return request.redirect('/portal')

