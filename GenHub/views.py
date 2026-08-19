import discord
from discord.ui import View, Button, button


class PaginatedEmbedView(View):
    """Interactive paginated embed view with Previous/Next buttons."""

    def __init__(self, pages: list, author_id: int, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self._update_buttons()

    def _update_buttons(self):
        if not self.pages:
            self.prev_button.disabled = True
            self.next_button.disabled = True
            self.page_indicator.label = "Page 0/0"
            return

        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1
        self.page_indicator.label = f"Page {self.current_page + 1} / {len(self.pages)}"

    @button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="btn_prev")
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can navigate pages.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @button(label="Page 1 / 1", style=discord.ButtonStyle.primary, disabled=True, custom_id="btn_page")
    async def page_indicator(self, interaction: discord.Interaction, button: Button):
        pass

    @button(label="Next ▶️", style=discord.ButtonStyle.secondary, custom_id="btn_next")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can navigate pages.", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
