from odoo import models, api, fields
from odoo.exceptions import ValidationError, UserError
from datetime import date
from odoo import http
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome # type: ignore




# =====================
# Project Project
# =====================
class ProjectProject(models.Model):
    _inherit = 'project.project'

    partner_id = fields.Many2one('res.partner', string='Klijent', help='Partner kome je projekat namijenjen.')
    team_ids = fields.Many2many('construction.team', string='Timovi')

# =====================
# Project Task
# =====================
class ProjectTask(models.Model):
    _inherit = 'project.task'

    offer_ids = fields.One2many('task.offer', 'task_id', string='Offers')
    budget = fields.Float(string="Budget")
    planned_date = fields.Date(string="Planned Date")
    contract_id = fields.Many2one('ir.attachment', string="Contract")
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        domain=[('res_model', '=', 'project.task')],
        help='Attachments related to this task'
    )

    user_id = fields.Many2one('res.users', string="Odgovorni korisnik")
    offer_count = fields.Integer(string='Broj ponuda', compute='_compute_offer_count')

    @api.depends('offer_ids')
    def _compute_offer_count(self):
        for task in self:
            task.offer_count = len(task.offer_ids)

    def action_view_task_offers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ponude za zadatak',
            'res_model': 'task.offer',
            'view_mode': 'tree,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }


# =====================
# Construction Team
# =====================
class ConstructionTeam(models.Model):
    _name = 'construction.team'
    _description = 'Konstrukcioni tim'

    name = fields.Char(string="Name", required = True)
    leader_id = fields.Many2one('res.users', string="Team Leader")
    member_ids = fields.Many2many('hr.employee', string="Team Members")

# =====================
# Offer
# =====================
class TaskOffer(models.Model):
    _name = 'task.offer'
    _description = 'Task Offer'

    name = fields.Char(string="Offer Name", required=True, help="Unique name for the offer")
    task_id = fields.Many2one('project.task',string="Task", required=True)
    team_id = fields.Many2one('construction.team', string="Team", required=True)
    price = fields.Float(string="Offer price")
    deadline = fields.Date(string="Deadline")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string="Status", default="draft", required=True)
    approval_ids = fields.One2many('offer.approval', 'offer_id', string='Odobrenja')
    approval_status = fields.Selection(related='approval_ids.state', string='Status odobrenja', readonly=True)
    agreement_template = fields.Binary(string="Ugovor za potpisivanje", attachment=True)
    agreement_template_filename = fields.Char(string="Naziv fajla ugovora")

    show_form_fields = fields.Boolean(compute='_compute_show_form_fields')

    def _compute_show_form_fields(self):
        for rec in self:
            rec.show_form_fields = bool(rec.id)



    @api.constrains('deadline')
    def _check_deadline_not_in_past(self):
        for record in self:
            if record.deadline and record.deadline < date.today():
                raise ValidationError("Deadline cannot be in the past.")
    
    def action_accept(self):
        for offer in self:
            approval = offer.approval_ids.filtered(lambda a: a.state == 'approved')
            if not approval:
                raise UserError("Ponuda ne može biti prihvaćena dok nije odobrena.")
            
            if offer.status in ('accepted', 'rejected'):
                raise UserError("Nije moguće prihvatiti već prihvaćenu ili odbijenu ponudu.")

            if not offer.agreement_template:
                raise UserError("Prije prihvatanja ponude morate priložiti dokument ugovora za potpisivanje.")

            offer.status = 'accepted'
            task = offer.task_id

            # Odbij ostale ponude
            other_offers = task.offer_ids.filtered(lambda o: o.id != offer.id)
            other_offers.write({'status': 'rejected'})

            # Postavi status zadatka
            if hasattr(task, 'status'):
                task.status = 'accepted'

            # Kreiraj ugovor ako ne postoji
            existing_contract = self.env['task.contract'].search([
                ('offer_id', '=', offer.id)
            ], limit=1)

            if not existing_contract:
                self.env['task.contract'].create({
                    'name': f'Ugovor: {task.name} - {offer.team_id.name}',
                    'task_id': task.id,
                    'team_id': offer.team_id.id,
                    'offer_id': offer.id,
                    'price': offer.price,
                    'start_date': task.planned_date,
                    'agreement_file': offer.agreement_template,
                    'agreement_file_filename': offer.agreement_template_filename,
                })

            # Notifikacije
            offer._notify_authors_on_acceptance()
            other_offers._notify_authors_on_rejection()



    def action_reject(self):
        for offer in self:
            if offer.status in ('accepted', 'rejected'):
                raise UserError("Nije moguće prihvatiti već prihvaćenu ili odbijenu ponudu.")
            offer.status = 'rejected'

    def _notify_authors_on_acceptance(self):
        template = self.env.ref('odoo_projekat_vjezba.email_template_offer_accepted')
        for offer in self:
            template.send_mail(offer.id, force_send=True)
       
    def _notify_authors_on_rejection(self):
        template = self.env.ref('odoo_projekat_vjezba.email_template_offer_rejected')
        for offer in self:
            template.send_mail(offer.id, force_send=True)

    def action_send_offer(self):
        for offer in self:
            offer.status = 'sent'
            if not offer.approval_ids:
                self.env['offer.approval'].create({
                    'offer_id': offer.id,
                    'approver_id': self.env.user.id,
                })

       
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            existing = self.search([
                ('task_id', '=', vals.get('task_id')),
                ('team_id', '=', vals.get('team_id')),
            ])
            if existing:
                raise ValidationError("Ovaj tim je već poslao ponudu za ovaj zadatak.")

        offers = super().create(vals_list)

        for offer in offers:
            if not offer.approval_ids:
                self.env['offer.approval'].create({
                    'offer_id': offer.id,
                    'approver_id': self.env.user.id,
                })

        return offers






# =====================
# Contract
# =====================
class TaskContract(models.Model):
    _name = 'task.contract'
    _description = 'Ugovor'

    name = fields.Char(string="Name", required=True)
    task_id = fields.Many2one('project.task', string="Task", required=True)
    team_id = fields.Many2one('construction.team', string="Team", required=True)
    offer_id = fields.Many2one('task.offer', string="Ponuda", ondelete='cascade')
    price = fields.Float(string="Contract Price")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    # 🟢 Admin uploaduje originalni ugovor
    agreement_file = fields.Binary(string="Ugovor za potpisivanje", attachment=True)
    agreement_file_filename = fields.Char(string="Naziv ugovora za potpisivanje")
    agreement_file_date = fields.Datetime("Datum postavljanja originalnog ugovora")

    # 🟡 Portal korisnik uploaduje svoj potpisani ugovor
    user_signed_agreement = fields.Binary(string="Potpisani ugovor od korisnika", attachment=True)
    user_signed_agreement_filename = fields.Char(string="Naziv korisničkog ugovora")
    user_signed_agreement_date = fields.Datetime("Datum slanja potpisanog ugovora od korisnika")

    # 🔵 Admin uploaduje potpisani ugovor
    admin_signed_agreement = fields.Binary(string="Potpisani ugovor od admina", attachment=True)
    admin_signed_agreement_filename = fields.Char(string="Naziv adminovog ugovora")
    admin_signed_agreement_date = fields.Datetime("Datum slanja potpisanog ugovora od menadžera")

    # 📅 Statusi i potvrde
    is_signed = fields.Boolean(string="Ugovor potpisan", default=False)
    date_signed = fields.Date(string="Datum potpisa")

    status = fields.Selection([
        ('draft', 'Na čekanju'),
        ('uploaded', 'Potpisan od strane tima'),
        ('confirmed', 'Potvrđen od strane menadžera')
    ], string="Status", default='draft')
    


    def write(self, vals):
        for rec in self:
            now = fields.Datetime.now()

            # if vals.get('agreement_file') and not rec.agreement_file_date:
            #     vals['agreement_file_date'] = now

            if vals.get('user_signed_agreement'):
                vals['status'] = 'uploaded'
                vals['user_signed_agreement_date'] = now

            if vals.get('admin_signed_agreement'):
                vals['status'] = 'confirmed'
                vals['admin_signed_agreement_date'] = now

            # Ako oba postoje (stari + novi podaci)
            user_agreement = vals.get('user_signed_agreement') or rec.user_signed_agreement
            admin_agreement = vals.get('admin_signed_agreement') or rec.admin_signed_agreement

            if user_agreement and admin_agreement:
                vals['is_signed'] = True
                if not rec.date_signed:
                    vals['date_signed'] = date.today()

        return super().write(vals)




    def action_confirm_contract(self):
        for rec in self:
            if not rec.user_signed_agreement:
                raise UserError("Nema učitan potpisan ugovor od strane korisnika.")
            if not rec.admin_signed_agreement:
                raise UserError("Nema učitan potpisan ugovor od strane menadžera.")
            rec.status = 'confirmed'


    def _on_offer_change(self):
        if self.offer_id:
            self.task_id = self.offer_id.task_id
            self.team_id = self.offer_id.team_id



class OfferApproval(models.Model):
    _name = 'offer.approval'
    _description = 'Approval for Task Offer'

    offer_id = fields.Many2one('task.offer', required=True, ondelete='cascade', string='Ponuda')
    approver_id = fields.Many2one('res.users', string='Odobravalac', default=lambda self: self.env.user)
    state = fields.Selection([
        ('pending', 'Na čekanju'),
        ('approved', 'Odobreno'),
        ('rejected', 'Odbijeno')
    ], default='pending', string='Status')
    note = fields.Text(string='Napomena')

    show_approval_buttons = fields.Boolean(compute='_compute_show_approval_buttons', store=False)

    @api.depends('state')
    def _compute_show_approval_buttons(self):
        for rec in self:
            rec.show_approval_buttons = rec.state == 'pending'

    def action_approve(self):
        for record in self:
            record.state = 'approved'
        return True

    def action_reject(self):
        for record in self:
            record.state = 'rejected'
        return True


    


class InfoNotification(models.Model):
    _name = 'info.notification'
    _description = 'Info Tabla Obavještenje'
    _order = 'create_date desc'

    name = fields.Char('Naslov', required=True)
    body = fields.Text('Poruka', required=True)
    author_id = fields.Many2one('res.users', string='Autor', default=lambda self: self.env.user)
    comment_ids = fields.One2many('info.notification.comment', 'notification_id', string='Komentari')


class InfoNotificationComment(models.Model):
    _name = 'info.notification.comment'
    _description = 'Komentar na obavještenje'
    _order = 'create_date asc'

    body = fields.Text('Komentar', required=True)
    author_id = fields.Many2one('res.users', string='Autor', default=lambda self: self.env.user)
    notification_id = fields.Many2one('info.notification', string='Obavještenje', required=True)


class InfoChatMessage(models.Model):
    _name = 'info.chat.message'
    _description = 'Privatna poruka (chat)'
    _order = 'create_date desc'

    body = fields.Text('Poruka', required=True)
    sender_id = fields.Many2one('res.users', string='Pošiljalac', default=lambda self: self.env.user)
    receiver_id = fields.Many2one('res.users', string='Primalac', required=True)
