import click

from naqel.setup import after_install as setup


def after_install():
	try:
		print("Setting up Naqel...")
		setup()

		click.secho("Thank you for installing Naqel!", fg="green")

	except Exception as e:
		BUG_REPORT_URL = "https://github.com/QualityPoint/naqel/issues/new"
		click.secho(
			"Installation for Naqel app failed due to an error."
			" Please try re-installing the app or"
			f" report the issue on {BUG_REPORT_URL} if not resolved.",
			fg="bright_red",
		)
		raise e
