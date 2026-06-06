/*
CAR-T + IL-15 boundary-sourced immune-tumor model (2D).
No vessels, no hepatocytes. Oxygen and IL-15 are boundary Dirichlet.
*/

#include "./cancer_immune_3D.h"
#include <iomanip>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>

static inline double il15_hill( double x, double K, double n );

static int oxygen_index = -1;
static int il15_index = -1;
static int aux_index = -1;
static int ifng_index = -1;

Cell_Definition* tumor_cell_definition = NULL;
Cell_Definition* car_t_cell_definition = NULL;
Cell_Definition* naive_t_cell_definition = NULL;
Cell_Definition* cd8_t_cell_definition = NULL;
Cell_Definition* exhausted_t_cell_definition = NULL;
Cell_Definition* macrophage_m0_cell_definition = NULL;
Cell_Definition* macrophage_m1_cell_definition = NULL;
Cell_Definition* macrophage_m2_cell_definition = NULL;

int tumor_cell_type = 0;
int car_t_cell_type = 1;
int naive_t_cell_type = 2;
int cd8_t_cell_type = 3;
int exhausted_t_cell_type = 4;
int macrophage_m0_cell_type = 5;
int macrophage_m1_cell_type = 6;
int macrophage_m2_cell_type = 7;

const int T_STATE_NAIVE = 0;
const int T_STATE_EFFECTOR = 1;
const int T_STATE_EXHAUSTED = 2;

const int M_STATE_M0 = 0;
const int M_STATE_M1 = 1;
const int M_STATE_M2 = 2;

double IL15_C_baseline = 0.0;
double IL15_C_dose = 0.0;
double IL15_on_duration_min = 60.0;
double IL15_start_time_min = 0.0;
double IL15_period_min = 1440.0;
double IL15_free_half_life_min = 900.0;
double IL15_decay_rate = 0.0;

// Helper cytokine (aux) + IFNg settings
static std::string aux_cytokine_name = "IL15";
static std::string aux_mode = "bath";
static double aux_bath_dose = 1.0;
static bool aux_keep_constant = true;
static double aux_refill_period_min = 0.0;
static double qmax_aux_engineered = 0.05;
static double qmax_aux_endogenous_IL2 = 0.02;
static double qmax_aux_endogenous_IL21 = 0.01;
static bool enable_endogenous_autocrine_for_IL2_IL21 = true;
static double aux_half_life_IL2_min = 240.0;
static double aux_half_life_IL7_min = 720.0;
static double aux_half_life_IL15_min = 720.0;
static double aux_half_life_IL18_min = 720.0;

static bool enable_IFNg_PDL1_feedback = true;
static double qIFNg_max = 0.03;
static double IFNg_secretion_target = 1.0;
static double alpha_IFNg_aux = 0.5;
static double K_IFNg_PDL1 = 0.5;
static double n_IFNg_PDL1 = 2.0;
static double k_PDL1_up = 0.01;
static double k_PDL1_down = 0.001;
static double K_PDL1_inhib = 0.5;
static double n_PDL1_inhib = 2.0;

// CAR-T activation / exhaustion / killing modulation
static double K_A = 0.5;
static double n_A = 2.0;
static double tumor_antigen_density = 1.0;
static double k_act = 0.05;
static double k_off = 0.01;
static double k_exh = 0.01;
static double k_rec_cart = 0.002;
static double r0_cart = 0.0005;
static double eps_a = 0.05;
static double lambda0_cart = 0.0002;
static double lambda_AICD = 0.0005;
static double p_AICD = 2.0;
static double k0_attack = 0.2;
static double dmg0 = 0.02;
static double m_dmg = 2.0;
static double attack_duration_min = 30.0;
static double k_rep = 0.001;
static double Dcrit = 1.0;
static double damage_Vmax = 0.2;
static double damage_Ksat = 0.1;

static double aux_uptake_rate = 0.05;
static double aux_secretion_Ksat = 5.0;

struct AuxCytokineParams
{
	bool use_gate = false;
	double K_cyto = 0.4;
	double n_cyto = 2.0;
	double alpha_prolif = 1.0;
	double alpha_surv = 1.0;
	double alpha_cyto = 1.0;
	double alpha_exh = 1.0;
	double beta_AICD = 0.0;
	bool endogenous_autocrine_allowed = false;
};

static AuxCytokineParams aux_params;

static double get_aux_half_life_min( const std::string& name )
{
	// Use user-defined values for cytokines explicitly requested by the user.
	// Fall back to the XML substrate decay for others (e.g., IL12 / IL21).
	if( name == "IL2" ) { return aux_half_life_IL2_min; }
	if( name == "IL7" ) { return aux_half_life_IL7_min; }
	if( name == "IL15" ) { return aux_half_life_IL15_min; }
	if( name == "IL18" ) { return aux_half_life_IL18_min; }
	return -1.0;
}

double metrics_interval_min = 60.0;
double snapshot_interval_min = 60.0;
double z_slice_thickness = 10.0;
int png_width = 700;
int png_height = 700;

double IL15_AUC_total = 0.0;
double tumor_AUC = 0.0;
double cumulative_tumor_kills = 0.0;
double cumulative_tumor_kills_CAR_T = 0.0;
double cumulative_tumor_kills_CD8 = 0.0;
double cumulative_car_t_deaths = 0.0;
double cumulative_exhausted_car_t = 0.0;
double cumulative_terminal_exhausted_car_t = 0.0;
double cumulative_terminal_exhausted_cd8 = 0.0;
double w_auc = 0.1;

bool fast_test_mode = false;
double debug_center_o2_pre = 0.0;

static std::ofstream metrics_file;
static std::ofstream screening_file;
static std::ofstream car_t_kill_file;
static double next_metrics_time = 0.0;
static double last_cumulative_tumor_kills_car_t = 0.0;

static double tumor_base_prolif_rate = 0.000962;
static double tumor_O2_uptake_rate = 0.01;
static double immune_O2_uptake_rate = 0.01;
static double tumor_initial_radius = 50.0;
static int N_tumor0 = 500;
static double tumor_necrosis_rate = 0.0002;
static double tumor_necrosis_O2_half_max = 1.0;
static double tumor_necrosis_hill_power = 4.0;
static double tumor_prolif_O2_half_max = 12.0;
static double tumor_prolif_hill_power = 2.0;
static double tumor_prolif_min_multiplier = 0.0;
static double O2_quiescence_threshold = 5.0;
static double O2_necrosis_gate = 4.0;
static double necrosis_damage_threshold = 720.0;
static double hypoxia_damage_repair_rate = 2.0;
static double max_prolif_slowdown = 0.2;
static double hypoxia_motility_boost = 1.0;
static double hypoxia_persistence_boost = 0.7;
static double hypoxia_adhesion_drop = 0.5;
static double hypoxia_resistance_mult = 2.0;
static double tumor_damage_per_contact = 0.02;
static double tumor_damage_threshold = 1.0;
static double tumor_damage_necrosis_o2_threshold = 5.0;
static double phagocytosis_rate_M0 = 0.01;
static double phagocytosis_rate_M1 = 0.02;
static double phagocytosis_rate_M2 = 0.005;
static double tim3_gal9_strength = 0.0;
static double p_M0_to_M1 = 0.001;
static double p_M0_to_M2 = 0.001;
static double O2_hypoxia_threshold = 10.0;
static double O2_normoxia_threshold = 15.0;
static double k_antigen_present = 1.0;
static double antigen_contact_time_min = 10.0;
static size_t antigen_presentation_events = 0;
static double naive_to_cd8_antigen_threshold = 0.2;
static double naive_to_cd8_rate = 0.001;
static double naive_R_contact_APC = 15.0;
static double naive_priming_min_time = 60.0;
static double naive_priming_decay_rate = 0.002;
static double naive_apc_weight_m0 = 0.6;
static double naive_apc_weight_m1 = 1.0;
static double naive_apc_weight_m2 = 0.3;
static double p_base_M1_to_M2 = 0.0;
static double M1_to_M2_O2_half = 10.0;
static double M1_to_M2_hill_power = 2.0;
static double m1_necrosis_O2_gate = 6.0;
static double m1_necrosis_O2_halfmax = 8.0;
static double m1_necrosis_hill_power = 3.0;
static double m1_hypoxia_damage_rate = 1.0;
static double m1_hypoxia_damage_repair_rate = 0.3;
static double m1_necrosis_damage_threshold = 1.0;
static double m2_necrosis_O2_gate = 3.5;
static double m2_necrosis_O2_halfmax = 5.0;
static double m2_necrosis_hill_power = 3.0;
static double m2_hypoxia_damage_rate = 0.7;
static double m2_hypoxia_damage_repair_rate = 0.4;
static double m2_necrosis_damage_threshold = 1.2;
static double m1_base_speed = 0.5;
static double m1_base_persistence = 10.0;
static double m1_migration_bias = 0.3;
static double m1_margin_preferred_radius = 0.0;
static double m1_margin_band_width = 60.0;
static double m1_margin_bias_strength = 0.25;
static double m1_severe_hypoxia_O2 = 4.0;
static double m1_seek_naive_radius = 200.0;
static double m2_base_speed = 1.0;
static double m2_base_persistence = 30.0;
static double m2_migration_bias = 0.5;
static double m2_hypoxia_pref_min = 6.0;
static double m2_hypoxia_pref_max = 10.0;
static double m2_hypoxia_speed_boost = 1.4;
static double m2_hypoxia_persistence_boost = 1.8;

static int N_CAR_T0 = 100;
static int max_spawn_attempts = 100;
static double spawn_radius_from_boundary = 50.0;

static int number_of_naive_t_cells = 0;
static int number_of_cd8_t_cells = 0;
static int number_of_exhausted_t_cells = 0;
static int number_of_m0_macrophages = 0;
static int number_of_m1_macrophages = 0;
static int number_of_m2_macrophages = 0;

static double initial_min_immune_distance_from_tumor = 30.0;
static double thickness_of_immune_seeding_region = 75.0;

static double R_seek = 100.0;
static double R_attach_CAR_T = 20.0;
static double dwell_time_min_CAR_T = 30.0;
static double p_kill_CAR_T = 0.30;
static double car_t_prolif_rate = 0.0;
static double car_t_exhaust_prolif_halfmax = 0.0;
static double car_t_necrosis_O2_gate = 0.0;
static double car_t_necrosis_damage_rate = 0.0;
static double car_t_necrosis_damage_threshold = 0.0;
static double car_t_exhaustion_per_kill = 0.0;
static double car_t_exhaustion_rate_when_attached = 0.0;
static double car_t_exhaustion_threshold = 0.0;
static double car_t_exhausted_kill_multiplier = 0.0;
static double car_t_exhaustion_increase_per_division = 0.0;
static double car_t_exhaustion_max = 0.0;
static double car_t_terminal_exhaust_gate = 0.85;
static double car_t_terminal_exhaust_time_min = 360.0;
static double car_t_terminal_death_rate = 2e-4;

static double R_attach_CD8 = 15.0;
static double dwell_time_min_CD8 = 60.0;
static double p_kill_CD8 = 0.02;
static double cd8_prolif_rate = 0.0015;
static double cd8_exhaust_prolif_halfmax = 5.0;
static double cd8_exhaustion_increase_per_division = 0.05;
static double cd8_exhaustion_max = 1.0;
static double cd8_necrosis_O2_gate = 7.0;
static double cd8_necrosis_damage_rate = 1.5;
static double cd8_necrosis_damage_threshold = 0.7;
static double cd8_sense_radius = 200.0;
static double cd8_bias_max = 0.3;
static double cd8_terminal_exhaust_gate = 0.85;
static double cd8_terminal_exhaust_time_min = 360.0;
static double cd8_terminal_death_rate = 2e-4;

static double exhaustion_per_kill = 1.0;
static double exhaustion_threshold = 10.0;
static double exhausted_speed_multiplier = 0.5;
static double exhausted_kill_multiplier = 0.5;
static double exhaustion_rate_when_attached = 0.0001;
static double exhaustion_E_max = 10.0;
static double O2_hypoxia_halfmax = 8.0;
static double hypoxia_hill_n = 2.0;
static double hypoxia_exhaust_mult = 1.0;
static double M1_recovery_rate = 0.001;
static double M1_recovery_mult = 1.0;
static double M2_present_exhaust_rate = 0.002;
static double M2_present_exhaust_per_event = 0.05;
static double tumor_O2_hypoxia_threshold = 10.0;
static double tumor_base_hypoxia_speed = 0.2;
static double tumor_base_persistence_time = 30.0;
static double invasion_pressure_cutoff = 1.0;
static double invasion_fraction_max = 0.30;
static double invasion_noise_strength = 0.20;
static double invasion_grad_eps = 1e-6;
static std::vector<double> tumor_center = { 0.0, 0.0, 0.0 };

static void add_custom_var_if_missing( Cell_Definition* def, const std::string& name,
	const std::string& units, double value )
{
	if( def == NULL ) { return; }
	if( def->custom_data.find_variable_index( name ) >= 0 ) { return; }
	def->custom_data.add_variable( name, units, value );
}

static inline bool cells_in_contact( Cell* a, Cell* b )
{
	std::vector<double> dv = b->position - a->position;
	double r = a->phenotype.geometry.radius + b->phenotype.geometry.radius;
	return norm_squared( dv ) <= r * r;
}

static inline double fast_pow_n( double x, double n )
{
	if( n == 2.0 ) { return x * x; }
	if( n == 4.0 ) { double x2 = x * x; return x2 * x2; }
	return pow( x, n );
}

static AuxCytokineParams get_aux_params( const std::string& name )
{
	AuxCytokineParams p;
	p.n_cyto = 2.0;
	if( name == "IL2" )
	{
		p.use_gate = false;
		p.K_cyto = 0.3;
		p.alpha_prolif = 6.0;
		p.alpha_surv = 1.0;
		p.alpha_cyto = 1.0;
		p.alpha_exh = 1.5;
		p.beta_AICD = 1.0;
		p.endogenous_autocrine_allowed = true;
	}
	else if( name == "IL7" )
	{
		p.use_gate = false;
		p.K_cyto = 0.5;
		p.alpha_prolif = 2.0;
		p.alpha_surv = 4.0;
		p.alpha_cyto = 0.5;
		p.alpha_exh = 0.0;
		p.beta_AICD = 0.0;
		p.endogenous_autocrine_allowed = false;
	}
	else if( name == "IL15" )
	{
		p.use_gate = false;
		p.K_cyto = 0.4;
		p.alpha_prolif = 3.0;
		p.alpha_surv = 4.0;
		p.alpha_cyto = 3.0; // 3x stronger IL-15 effect on killing
		p.alpha_exh = -0.2;
		p.beta_AICD = 0.0;
		p.endogenous_autocrine_allowed = false;
	}
	else if( name == "IL12" )
	{
		p.use_gate = true;
		p.K_cyto = 0.2;
		p.alpha_prolif = 1.5;
		p.alpha_surv = 0.5;
		p.alpha_cyto = 3.0;
		p.alpha_exh = 2.0;
		p.beta_AICD = 1.5;
		p.endogenous_autocrine_allowed = false;
	}
	else if( name == "IL18" )
	{
		p.use_gate = true;
		p.K_cyto = 0.2;
		p.alpha_prolif = 1.5;
		p.alpha_surv = 1.0;
		p.alpha_cyto = 2.5;
		p.alpha_exh = 0.8;
		p.beta_AICD = 0.5;
		p.endogenous_autocrine_allowed = false;
	}
	else if( name == "IL21" )
	{
		p.use_gate = false;
		p.K_cyto = 0.4;
		p.alpha_prolif = 2.5;
		p.alpha_surv = 2.0;
		p.alpha_cyto = 1.0;
		p.alpha_exh = -1.0;
		p.beta_AICD = 0.0;
		p.endogenous_autocrine_allowed = true;
	}
	return p;
}

static double il15_cis_signal( double c_local );
static double il15_trans_signal( double bsum, double K_trans );
static double il15_or_combine( double a, double b );
static void update_Tcell_IL15_module(
	double& E,
	double& R,
	double C,
	double Bsum,
	double dt,
	double O2,
	bool contact_with_tumor,
	bool contact_with_M2,
	bool contact_with_M1,
	bool attempted_kill,
	double& kill_rate,
	double& death_rate_eff,
	double Kd_cis_local,
	double n_cis_local,
	double K_trans_local,
	double w_cis_local,
	double w_trans_local,
	double k_rec_local,
	double k_int_local,
	double exhaustion_rate_when_attached,
	double exhaustion_per_kill,
	double M2_present_exhaust_rate_local,
	double M1_recovery_rate_local,
	double p_kill,
	double exhaustion_threshold_local,
	double exhausted_kill_multiplier_local,
	double death_rate_base,
	double tumor_resistance_mult,
	double O2_half,
	double hypoxia_hill,
	double hypoxia_exhaust_mult,
	double recovery_rate,
	double& il15_signal_out,
	double& cis_signal_out,
	double& trans_signal_out
);

struct NeighborContactInfo
{
	bool contact_tumor = false;
	bool contact_m0 = false;
	bool contact_m1 = false;
	bool contact_m2 = false;
	bool found_tumor = false;
	double il15_trans = 0.0;
	std::vector<double> dir_to_tumor = { 0.0, 0.0, 0.0 };
};

static NeighborContactInfo scan_neighbors( Cell* pCell, const std::vector<Cell*>& neighbors,
	bool need_il15_trans, bool need_nearest_tumor, bool need_contacts )
{
	NeighborContactInfo info;
	double best_d2 = 1e99;
	for( size_t i = 0; i < neighbors.size(); i++ )
	{
		Cell* pOther = neighbors[i];
		if( pOther == pCell ) { continue; }
		std::vector<double> dv = pOther->position - pCell->position;
		double d2 = norm_squared( dv );
		double contact_dist = pOther->phenotype.geometry.radius + pCell->phenotype.geometry.radius;
		double contact_dist2 = contact_dist * contact_dist;

		if( need_nearest_tumor && pOther->type == tumor_cell_type )
		{
			if( d2 < best_d2 )
			{
				best_d2 = d2;
				info.dir_to_tumor = dv;
				info.found_tumor = true;
			}
		}

		if( !need_contacts && !need_il15_trans ) { continue; }
		if( d2 > contact_dist2 ) { continue; }

		if( pOther->type == tumor_cell_type ) { info.contact_tumor = true; }
		if( pOther->type == macrophage_m0_cell_type ) { info.contact_m0 = true; }
		if( pOther->type == macrophage_m1_cell_type ) { info.contact_m1 = true; }
		if( pOther->type == macrophage_m2_cell_type ) { info.contact_m2 = true; }

		if( need_il15_trans )
		{
			if( pOther->type == macrophage_m0_cell_type || pOther->type == macrophage_m1_cell_type )
			{
				info.il15_trans += pOther->custom_data["macrophage_bound_IL15"];
			}
		}
	}
	return info;
}

static double tumor_antigen_activation( Cell* pTarget )
{
	if( pTarget == NULL || pTarget->type != tumor_cell_type ) { return 0.0; }
	int antigen_index = pTarget->custom_data.find_variable_index( "antigen" );
	if( antigen_index < 0 ) { return 1.0; }
	double antigen = pTarget->custom_data.variables[antigen_index].value;
	return il15_hill( antigen, K_A, n_A );
}

static int idx_exhaustion_car_t = -1;
static int idx_il15_signal_car_t = -1;
static int idx_exhaustion_cd8 = -1;
static int idx_is_exhausted_cd8 = -1;
static int idx_is_terminal_cd8 = -1;
static int idx_exhausted_origin_is_car_t = -1;
static void ensure_custom_data_on_all_cell_definitions( void )
{
	std::vector<Cell_Definition*> defs = {
		tumor_cell_definition,
		car_t_cell_definition,
		naive_t_cell_definition,
		cd8_t_cell_definition,
		exhausted_t_cell_definition,
		macrophage_m0_cell_definition,
		macrophage_m1_cell_definition,
		macrophage_m2_cell_definition
	};

	struct CustomVar
	{
		const char* name;
		const char* units;
		double value;
	};

	const CustomVar vars[] = {
		{ "exhaustion", "dimensionless", 0.0 },
		{ "is_exhausted", "dimensionless", 0.0 },
		{ "is_terminal_exhausted", "dimensionless", 0.0 },
		{ "time_high_exhaustion", "min", 0.0 },
		{ "il15_signal", "dimensionless", 0.0 },
		{ "il15_receptor", "dimensionless", 1.0 },
		{ "attachment_rate", "1/min", 0.0 },
		{ "kill_rate", "1/min", 0.0 },
		{ "attachment_lifetime", "min", 0.0 },
		{ "max_attachment_distance", "micron", 0.0 },
		{ "antigen_signal", "dimensionless", 0.0 },
		{ "time_attached", "min", 0.0 },
		{ "attempted_kill_this_step", "dimensionless", 0.0 },
		{ "exhaustion_increase_per_division", "dimensionless", 0.0 },
		{ "exhaustion_max", "dimensionless", 0.0 },
		{ "time_contact_APC", "min", 0.0 },
		{ "cd8_necrosis_O2_gate", "mmHg", 0.0 },
		{ "cd8_necrosis_damage_rate", "1/min", 0.0 },
		{ "cd8_necrosis_damage_threshold", "dimensionless", 0.0 },
		{ "naive_hypoxia_damage", "dimensionless", 0.0 },
		{ "cd8_hypoxia_damage", "dimensionless", 0.0 },
		{ "cd8_terminal_exhaust_gate", "dimensionless", 0.0 },
		{ "cd8_terminal_exhaust_time_min", "min", 0.0 },
		{ "cd8_terminal_death_rate", "1/min", 0.0 },
		{ "cd8_kill_mult", "dimensionless", 0.0 },
		{ "exhausted_origin_is_CAR_T", "dimensionless", 0.0 },
		{ "macrophage_bound_IL15", "dimensionless", 0.0 },
		{ "can_present_antigen", "dimensionless", 0.0 },
		{ "TIM3_Gal9_strength", "dimensionless", 0.0 },
		{ "m1_necrosis_O2_gate", "mmHg", 0.0 },
		{ "m1_necrosis_O2_halfmax", "mmHg", 0.0 },
		{ "m1_necrosis_hill_power", "dimensionless", 0.0 },
		{ "m1_hypoxia_damage_rate", "1/min", 0.0 },
		{ "m1_hypoxia_damage_repair_rate", "1/min", 0.0 },
		{ "m1_necrosis_damage_threshold", "dimensionless", 0.0 },
		{ "m1_hypoxia_damage", "dimensionless", 0.0 },
		{ "m2_necrosis_O2_gate", "mmHg", 0.0 },
		{ "m2_necrosis_O2_halfmax", "mmHg", 0.0 },
		{ "m2_necrosis_hill_power", "dimensionless", 0.0 },
		{ "m2_hypoxia_damage_rate", "1/min", 0.0 },
		{ "m2_hypoxia_damage_repair_rate", "1/min", 0.0 },
		{ "m2_necrosis_damage_threshold", "dimensionless", 0.0 },
		{ "m2_hypoxia_damage", "dimensionless", 0.0 },
		{ "damage", "dimensionless", 0.0 },
		{ "last_damage_from_type", "dimensionless", -1.0 },
		{ "hypoxia_damage", "dimensionless", 0.0 },
		{ "base_prolif_rate", "1/min", 0.0 },
		{ "base_migration_speed", "micron/min", 0.0 },
		{ "base_persistence_time", "min", 0.0 },
		{ "base_adhesion_strength", "dimensionless", 0.0 },
		{ "tumor_resistance_mult", "dimensionless", 0.0 },
		{ "car_t_hypoxia_damage", "dimensionless", 0.0 }
	};

	for( size_t i = 0; i < defs.size(); i++ )
	{
		for( size_t j = 0; j < sizeof( vars ) / sizeof( vars[0] ); j++ )
		{
			add_custom_var_if_missing( defs[i], vars[j].name, vars[j].units, vars[j].value );
		}
	}
}

static void debug_cell_motility_bias( Cell* pCell, const char* label )
{
	std::vector<double> to_tumor = tumor_center - pCell->position;
	double d = norm( to_tumor );
	std::vector<double> to_hat = UniformOnUnitSphere();
	if( d > 1e-12 )
	{
		to_hat = ( 1.0 / d ) * to_tumor;
	}

	std::vector<double> dir = pCell->phenotype.motility.migration_bias_direction;
	double norm_dir = norm( dir );
	if( norm_dir > 1e-12 )
	{
		dir *= ( 1.0 / norm_dir );
	}

	if( default_microenvironment_options.simulate_2D )
	{
		to_hat[2] = 0.0;
		dir[2] = 0.0;
		double norm_to_xy = std::sqrt( to_hat[0] * to_hat[0] + to_hat[1] * to_hat[1] );
		double norm_dir_xy = std::sqrt( dir[0] * dir[0] + dir[1] * dir[1] );
		if( norm_to_xy > 1e-12 )
		{
			to_hat[0] /= norm_to_xy;
			to_hat[1] /= norm_to_xy;
		}
		if( norm_dir_xy > 1e-12 )
		{
			dir[0] /= norm_dir_xy;
			dir[1] /= norm_dir_xy;
		}
	}

	double dp_dir = dir[0] * to_hat[0] + dir[1] * to_hat[1] + dir[2] * to_hat[2];
	double b = pCell->phenotype.motility.migration_bias;
	std::cout << label << " id=" << pCell->ID << " b=" << b << " dp_dir=" << dp_dir << std::endl;
}

static double Bmax_Mphi = 1.0;
static double k_on_Mphi = 0.02;
static double k_off_Mphi = 0.00077;
static double Kd_cis = 1.0;
static double n_cis = 1.5;
static double K_trans_CART = 0.5;
static double K_trans_CD8 = 1.0;
static double w_trans_CART = 1.0;
static double w_cis_CART = 0.3;
static double w_trans_CD8 = 0.20;
static double w_cis_CD8 = 0.25;
static double k_int = 3e-4;
static double k_rec = 1e-4;
static double alpha_death_CART = 0.60;
static double alpha_exh_CART = 0.50;
static double alpha_prolif_CART = 0.20;
static double alpha_death_CD8 = 0.35;
static double alpha_exh_CD8 = 0.25;
static double alpha_prolif_CD8 = 0.10;
static double beta_exh = 3.0;
static double beta_kill = 1.5;
static double beta_surv = 0.6;
static double K_exh = 0.3;
static double K_kill = 0.3;
static double K_surv = 0.3;
static double car_t_exhaustion_recovery_rate = 2e-4;
static double cd8_exhaustion_recovery_rate = 1.5e-4;
static double il15_cis_consume_rate = 1.0;
static double il15_trans_consume_rate = 1.0;
static double car_t_base_apoptosis_rate = 0.0;
static double cd8_base_apoptosis_rate = 0.0;
// IL10/IFNg are disabled in this variant (no cytokine signaling).

static double O2_boundary_value = 38.0;

static int apoptosis_index = 0;
static int necrosis_index = 1;

static bool car_t_spawned_once = false;

static double next_snapshot_time = 0.0;
static int frame_id = 0;
static bool snap_day3_done = false;
static bool snap_day5_done = false;
static bool snap_day7_done = false;

static std::vector<std::string> tumor_immune_cell_coloring( Cell* pCell )
{
	std::vector<std::string> out = paint_by_number_cell_coloring( pCell );
	if( pCell )
	{
		int exh_index = pCell->custom_data.find_variable_index( "exhaustion" );
		int term_index = pCell->custom_data.find_variable_index( "is_terminal_exhausted" );
		bool cd8_terminal = ( pCell->type == cd8_t_cell_type ) &&
			( term_index >= 0 && pCell->custom_data["is_terminal_exhausted"] > 0.5 );
		if( cd8_terminal )
		{
			const std::string exhausted_blue = "#1E3A8A";
			out[0] = exhausted_blue;
			out[2] = exhausted_blue;
			out[3] = exhausted_blue;
		}
	}
	if( pCell && pCell->type == exhausted_t_cell_type )
	{
		const std::string exhausted_color = "#1E3A8A";
		out[0] = exhausted_color;
		out[2] = exhausted_color;
		out[3] = exhausted_color;
	}
	return out;
}

static void strip_svg_time_and_agents( const std::string& filename )
{
	std::ifstream in( filename.c_str() );
	if( !in.good() ) { return; }
	std::vector<std::string> out_lines;
	std::vector<std::string> block;
	bool in_text = false;
	std::string line;
	while( std::getline( in, line ) )
	{
		if( !in_text && line.find( "<text" ) != std::string::npos )
		{
			in_text = true;
			block.clear();
			block.push_back( line );
			continue;
		}
		if( in_text )
		{
			block.push_back( line );
			if( line.find( "</text>" ) != std::string::npos )
			{
				in_text = false;
			}
			continue;
		}
		out_lines.push_back( line );
	}
	in.close();

	std::ofstream out( filename.c_str(), std::ios::out | std::ios::trunc );
	for( size_t i = 0; i < out_lines.size(); i++ )
	{
		out << out_lines[i] << "\n";
	}
}

static void initialize_metrics_file( void )
{
	std::string ts_path = PhysiCell_settings.folder + "/time_series.csv";
	metrics_file.open( ts_path.c_str(), std::ios::out );
	metrics_file.setf( std::ios::scientific );
	metrics_file << std::setprecision( 10 );
	// IL15 SWEEP ADDITION
	metrics_file << "time_min,time_day,"
	             << "tumor_count,CAR_T_count,cumulative_exhausted_CAR_T,"
	             << "terminal_exhausted_CAR_T_flag_count,cumulative_terminal_exhausted_CAR_T,"
	             << "cumulative_tumor_kills,cumulative_tumor_kills_CAR_T,"
	             << "mean_exhaustion_CAR_T,mean_IL15_signal_on_CAR_T,exhaustion_fraction_CAR_T,"
	             << "cumulative_car_t_deaths"
	             << std::endl;

	std::string kill_path = PhysiCell_settings.folder + "/car_t_kill_events.csv";
	car_t_kill_file.open( kill_path.c_str(), std::ios::out );
	car_t_kill_file.setf( std::ios::scientific );
	car_t_kill_file << std::setprecision( 10 );
	car_t_kill_file << "time_min,attacker_id,target_id,target_x,target_y,target_z,target_antigen,target_PDL1"
	                << std::endl;
}

static void log_car_t_kill_event( Cell* pAttacker, Cell* pTarget )
{
	if( !car_t_kill_file.is_open() || pAttacker == NULL || pTarget == NULL ) { return; }
	double antigen = 0.0;
	int antigen_index = pTarget->custom_data.find_variable_index( "antigen" );
	if( antigen_index >= 0 ) { antigen = pTarget->custom_data.variables[antigen_index].value; }
	double pdl1 = 0.0;
	int pdl1_index = pTarget->custom_data.find_variable_index( "PDL1" );
	if( pdl1_index >= 0 ) { pdl1 = pTarget->custom_data.variables[pdl1_index].value; }
	#pragma omp critical(car_t_kill_event_log)
	{
		car_t_kill_file << PhysiCell_globals.current_time << ","
		                << pAttacker->ID << ","
		                << pTarget->ID << ","
		                << pTarget->position[0] << ","
		                << pTarget->position[1] << ","
		                << pTarget->position[2] << ","
		                << antigen << ","
		                << pdl1
		                << std::endl;
		car_t_kill_file.flush();
	}
}

static void car_t_cell_division_function( Cell* pParent, Cell* pChild )
{
	if( pParent == NULL || pChild == NULL ) { return; }
	double inc = pParent->custom_data["exhaustion_increase_per_division"];
	double emax = pParent->custom_data["exhaustion_max"];
	double parent_e = pParent->custom_data["exhaustion"];
	double child_e = pChild->custom_data["exhaustion"];
	parent_e = std::min( emax, parent_e + inc );
	child_e = std::min( emax, child_e + inc );
	pParent->custom_data["exhaustion"] = parent_e;
	pChild->custom_data["exhaustion"] = child_e;
}

static void cd8_cell_division_function( Cell* pParent, Cell* pChild )
{
	if( pParent == NULL || pChild == NULL ) { return; }
	double inc = pParent->custom_data["exhaustion_increase_per_division"];
	double emax = pParent->custom_data["exhaustion_max"];
	double parent_e = pParent->custom_data["exhaustion"];
	double child_e = pChild->custom_data["exhaustion"];
	parent_e = std::min( parent_e + inc, emax );
	child_e = std::min( child_e + inc, emax );
	pParent->custom_data["exhaustion"] = parent_e;
	pChild->custom_data["exhaustion"] = child_e;
}

static double boundary_il15_value( double t )
{
	(void) t;
	// Continuous IL-15 only.
	return IL15_C_baseline;
}

static double boundary_aux_value( double t )
{
	(void) t;
	return aux_bath_dose;
}

void update_vessel_dirichlet_conditions( void )
{
	double il15_value = boundary_il15_value( PhysiCell_globals.current_time );
	double aux_value = boundary_aux_value( PhysiCell_globals.current_time );
	Microenvironment_Options& opt = default_microenvironment_options;
	static double next_il15_debug_time = 0.0;
	static double next_aux_refill_time = 0.0;
	if( PhysiCell_globals.current_time + 1e-9 >= next_il15_debug_time )
	{
		std::cout << "AUX boundary value = " << aux_value
		          << " at t=" << PhysiCell_globals.current_time << " min" << std::endl;
		next_il15_debug_time += metrics_interval_min;
	}
	if( il15_index >= 0 && il15_index < (int)opt.Dirichlet_condition_vector.size() )
	{
		opt.Dirichlet_condition_vector[il15_index] = il15_value;
		opt.Dirichlet_activation_vector[il15_index] = true;
		opt.Dirichlet_all[il15_index] = false;
		opt.Dirichlet_xmin[il15_index] = true;
		opt.Dirichlet_xmax[il15_index] = true;
		opt.Dirichlet_ymin[il15_index] = true;
		opt.Dirichlet_ymax[il15_index] = true;
		opt.Dirichlet_zmin[il15_index] = false;
		opt.Dirichlet_zmax[il15_index] = false;
		opt.Dirichlet_xmin_values[il15_index] = il15_value;
		opt.Dirichlet_xmax_values[il15_index] = il15_value;
		opt.Dirichlet_ymin_values[il15_index] = il15_value;
		opt.Dirichlet_ymax_values[il15_index] = il15_value;
		opt.Dirichlet_zmin_values[il15_index] = il15_value;
		opt.Dirichlet_zmax_values[il15_index] = il15_value;
	}
	if( oxygen_index >= 0 && oxygen_index < (int)opt.Dirichlet_condition_vector.size() )
	{
		opt.Dirichlet_condition_vector[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_activation_vector[oxygen_index] = true;
		opt.Dirichlet_all[oxygen_index] = false;
		opt.Dirichlet_xmin[oxygen_index] = true;
		opt.Dirichlet_xmax[oxygen_index] = true;
		opt.Dirichlet_ymin[oxygen_index] = true;
		opt.Dirichlet_ymax[oxygen_index] = true;
		opt.Dirichlet_zmin[oxygen_index] = false;
		opt.Dirichlet_zmax[oxygen_index] = false;
		opt.Dirichlet_xmin_values[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_xmax_values[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_ymin_values[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_ymax_values[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_zmin_values[oxygen_index] = O2_boundary_value;
		opt.Dirichlet_zmax_values[oxygen_index] = O2_boundary_value;
	}

	// Aux cytokine bath dosing: keep boundary constant if enabled, or periodic refill.
	if( aux_index >= 0 && aux_index < (int)opt.Dirichlet_condition_vector.size() )
	{
		if( aux_keep_constant )
		{
			opt.Dirichlet_condition_vector[aux_index] = aux_value;
			opt.Dirichlet_activation_vector[aux_index] = true;
			opt.Dirichlet_all[aux_index] = false;
			opt.Dirichlet_xmin[aux_index] = true;
			opt.Dirichlet_xmax[aux_index] = true;
			opt.Dirichlet_ymin[aux_index] = true;
			opt.Dirichlet_ymax[aux_index] = true;
			opt.Dirichlet_zmin[aux_index] = false;
			opt.Dirichlet_zmax[aux_index] = false;
			opt.Dirichlet_xmin_values[aux_index] = aux_value;
			opt.Dirichlet_xmax_values[aux_index] = aux_value;
			opt.Dirichlet_ymin_values[aux_index] = aux_value;
			opt.Dirichlet_ymax_values[aux_index] = aux_value;
			opt.Dirichlet_zmin_values[aux_index] = aux_value;
			opt.Dirichlet_zmax_values[aux_index] = aux_value;
		}
		else if( aux_refill_period_min > 0.0 && PhysiCell_globals.current_time + 1e-9 >= next_aux_refill_time )
		{
			for( int v = 0; v < microenvironment.number_of_voxels(); v++ )
			{
				microenvironment.density_vector(v)[aux_index] = aux_value;
			}
			next_aux_refill_time = PhysiCell_globals.current_time + aux_refill_period_min;
		}
	}

	// Explicitly clamp IL-15 on boundary voxels to avoid zero-field artifacts.
	if( il15_index >= 0 )
	{
		double xmin = microenvironment.mesh.bounding_box[0];
		double ymin = microenvironment.mesh.bounding_box[1];
		double xmax = microenvironment.mesh.bounding_box[3];
		double ymax = microenvironment.mesh.bounding_box[4];
		double dx = microenvironment.mesh.dx;
		double dy = microenvironment.mesh.dy;
		double epsx = 0.5 * dx + 1e-12;
		double epsy = 0.5 * dy + 1e-12;
		for( int v = 0; v < microenvironment.number_of_voxels(); v++ )
		{
			const std::vector<double>& c = microenvironment.mesh.voxels[v].center;
			bool on_x = ( std::fabs( c[0] - xmin ) <= epsx ) || ( std::fabs( c[0] - xmax ) <= epsx );
			bool on_y = ( std::fabs( c[1] - ymin ) <= epsy ) || ( std::fabs( c[1] - ymax ) <= epsy );
			if( on_x || on_y )
			{
				microenvironment.is_dirichlet_node( v ) = true;
				microenvironment.set_substrate_dirichlet_activation( il15_index, v, true );
				microenvironment.update_dirichlet_node( v, il15_index, il15_value );
				microenvironment.density_vector(v)[il15_index] = il15_value;
			}
		}
	}
	// Explicitly clamp aux cytokine on boundary voxels when in bath mode.
	if( aux_index >= 0 && aux_keep_constant )
	{
		double xmin = microenvironment.mesh.bounding_box[0];
		double ymin = microenvironment.mesh.bounding_box[1];
		double xmax = microenvironment.mesh.bounding_box[3];
		double ymax = microenvironment.mesh.bounding_box[4];
		double dx = microenvironment.mesh.dx;
		double dy = microenvironment.mesh.dy;
		double epsx = 0.5 * dx + 1e-12;
		double epsy = 0.5 * dy + 1e-12;
		for( int v = 0; v < microenvironment.number_of_voxels(); v++ )
		{
			const std::vector<double>& c = microenvironment.mesh.voxels[v].center;
			bool on_x = ( std::fabs( c[0] - xmin ) <= epsx ) || ( std::fabs( c[0] - xmax ) <= epsx );
			bool on_y = ( std::fabs( c[1] - ymin ) <= epsy ) || ( std::fabs( c[1] - ymax ) <= epsy );
			if( on_x || on_y )
			{
				microenvironment.is_dirichlet_node( v ) = true;
				microenvironment.set_substrate_dirichlet_activation( aux_index, v, true );
				microenvironment.update_dirichlet_node( v, aux_index, aux_value );
				microenvironment.density_vector(v)[aux_index] = aux_value;
			}
		}
	}
	// Force-apply Dirichlet conditions after updating per-voxel values.
	microenvironment.apply_dirichlet_conditions();
}

void setup_microenvironment( void )
{
	fast_test_mode = false;
	default_microenvironment_options.simulate_2D = true;
	default_microenvironment_options.dx = 20.0;
	default_microenvironment_options.dy = 20.0;
	default_microenvironment_options.dz = 20.0;
	default_microenvironment_options.outer_Dirichlet_conditions = true;
	initialize_microenvironment();

	oxygen_index = microenvironment.find_density_index( "oxygen" );
	il15_index = microenvironment.find_density_index( "IL15" );
	aux_index = microenvironment.find_density_index( "aux_cytokine" );
	ifng_index = microenvironment.find_density_index( "IFNg" );
	if( oxygen_index < 0 || il15_index < 0 || aux_index < 0 || ifng_index < 0 )
	{
		std::cout << "Error: missing substrate indices. Found:" << std::endl;
		for( size_t i = 0; i < microenvironment.density_names.size(); i++ )
		{
			std::cout << "  [" << i << "] " << microenvironment.density_names[i] << std::endl;
		}
		exit( -1 );
	}
	default_microenvironment_options.Dirichlet_activation_vector[oxygen_index] = true;
	default_microenvironment_options.Dirichlet_activation_vector[il15_index] = true;
	default_microenvironment_options.Dirichlet_activation_vector[aux_index] = false;
	default_microenvironment_options.Dirichlet_activation_vector[ifng_index] = false;
	default_microenvironment_options.Dirichlet_all[oxygen_index] = false;
	default_microenvironment_options.Dirichlet_all[il15_index] = false;
	default_microenvironment_options.Dirichlet_xmin[oxygen_index] = true;
	default_microenvironment_options.Dirichlet_xmax[oxygen_index] = true;
	default_microenvironment_options.Dirichlet_ymin[oxygen_index] = true;
	default_microenvironment_options.Dirichlet_ymax[oxygen_index] = true;
	default_microenvironment_options.Dirichlet_zmin[oxygen_index] = false;
	default_microenvironment_options.Dirichlet_zmax[oxygen_index] = false;
	default_microenvironment_options.Dirichlet_xmin[il15_index] = true;
	default_microenvironment_options.Dirichlet_xmax[il15_index] = true;
	default_microenvironment_options.Dirichlet_ymin[il15_index] = true;
	default_microenvironment_options.Dirichlet_ymax[il15_index] = true;
	default_microenvironment_options.Dirichlet_zmin[il15_index] = false;
	default_microenvironment_options.Dirichlet_zmax[il15_index] = false;

	IL15_free_half_life_min = parameters.doubles("IL15_free_half_life_min");
	IL15_decay_rate = log( 2.0 ) / IL15_free_half_life_min;
	microenvironment.decay_rates[il15_index] = IL15_decay_rate;
}

void create_cell_types( void )
{
	initialize_default_cell_definition();
	initialize_cell_definitions_from_pugixml();
	setup_signal_behavior_dictionaries();

	apoptosis_index = cell_defaults.phenotype.death.find_death_model_index( "apoptosis" );
	necrosis_index = cell_defaults.phenotype.death.find_death_model_index( "necrosis" );

	tumor_cell_definition = find_cell_definition( "tumor" );
	car_t_cell_definition = find_cell_definition( "CAR-T" );
	naive_t_cell_definition = find_cell_definition( "naive T cell" );
	cd8_t_cell_definition = find_cell_definition( "CD8 T cell" );
	exhausted_t_cell_definition = find_cell_definition( "exhausted T cell" );
	macrophage_m0_cell_definition = find_cell_definition( "macrophage M0" );
	macrophage_m1_cell_definition = find_cell_definition( "macrophage M1" );
	macrophage_m2_cell_definition = find_cell_definition( "macrophage M2" );

	// CD8 should use a dividing cycle (Ki67 advanced) so transition_rate(0,1) drives proliferation.
	cd8_t_cell_definition->functions.cycle_model = Ki67_advanced;
	cd8_t_cell_definition->phenotype.cycle.sync_to_cycle_model( Ki67_advanced );
	cd8_t_cell_definition->functions.cell_division_function = cd8_cell_division_function;
	// CAR-T clonal expansion uses a dividing cycle with exhaustion-suppressed entry.
	car_t_cell_definition->functions.cycle_model = Ki67_advanced;
	car_t_cell_definition->phenotype.cycle.sync_to_cycle_model( Ki67_advanced );
	car_t_cell_definition->functions.cell_division_function = car_t_cell_division_function;

	tumor_cell_type = tumor_cell_definition->type;
	car_t_cell_type = car_t_cell_definition->type;
	naive_t_cell_type = naive_t_cell_definition->type;
	cd8_t_cell_type = cd8_t_cell_definition->type;
	exhausted_t_cell_type = exhausted_t_cell_definition->type;
	macrophage_m0_cell_type = macrophage_m0_cell_definition->type;
	macrophage_m1_cell_type = macrophage_m1_cell_definition->type;
	macrophage_m2_cell_type = macrophage_m2_cell_definition->type;

	IL15_C_baseline = parameters.doubles("IL15_C_baseline");
	IL15_C_dose = parameters.doubles("IL15_C_dose");
	IL15_on_duration_min = parameters.doubles("IL15_on_duration_min");
	IL15_start_time_min = parameters.doubles("IL15_start_time_min");
	IL15_period_min = parameters.doubles("IL15_period_min");
	IL15_free_half_life_min = parameters.doubles("IL15_free_half_life_min");
	if( parameters.strings.find_index( "aux_cytokine_name" ) >= 0 )
	{
		aux_cytokine_name = parameters.strings("aux_cytokine_name");
	}
	if( parameters.strings.find_index( "aux_mode" ) >= 0 )
	{
		aux_mode = parameters.strings("aux_mode");
	}
	aux_bath_dose = parameters.doubles("aux_bath_dose");
	aux_keep_constant = parameters.bools("aux_keep_constant");
	aux_refill_period_min = parameters.doubles("aux_refill_period_min");
	qmax_aux_engineered = parameters.doubles("qmax_aux_engineered");
	qmax_aux_endogenous_IL2 = parameters.doubles("qmax_aux_endogenous_IL2");
	qmax_aux_endogenous_IL21 = parameters.doubles("qmax_aux_endogenous_IL21");
	enable_endogenous_autocrine_for_IL2_IL21 = parameters.bools("enable_endogenous_autocrine_for_IL2_IL21");
	aux_half_life_IL2_min = parameters.doubles("aux_half_life_IL2_min");
	aux_half_life_IL7_min = parameters.doubles("aux_half_life_IL7_min");
	aux_half_life_IL15_min = parameters.doubles("aux_half_life_IL15_min");
	aux_half_life_IL18_min = parameters.doubles("aux_half_life_IL18_min");

	if( aux_index >= 0 )
	{
		double aux_half_life_min = get_aux_half_life_min( aux_cytokine_name );
		if( aux_half_life_min > 0.0 )
		{
			microenvironment.decay_rates[aux_index] = log( 2.0 ) / aux_half_life_min;
		}
	}

	enable_IFNg_PDL1_feedback = parameters.bools("enable_IFNg_PDL1_feedback");
	qIFNg_max = parameters.doubles("qIFNg_max");
	IFNg_secretion_target = parameters.doubles("IFNg_secretion_target");
	alpha_IFNg_aux = parameters.doubles("alpha_IFNg_aux");
	K_IFNg_PDL1 = parameters.doubles("K_IFNg_PDL1");
	n_IFNg_PDL1 = parameters.doubles("n_IFNg_PDL1");
	k_PDL1_up = parameters.doubles("k_PDL1_up");
	k_PDL1_down = parameters.doubles("k_PDL1_down");
	K_PDL1_inhib = parameters.doubles("K_PDL1_inhib");
	n_PDL1_inhib = parameters.doubles("n_PDL1_inhib");

	K_A = parameters.doubles("K_A");
	n_A = parameters.doubles("n_A");
	tumor_antigen_density = parameters.doubles("tumor_antigen_density");
	k_act = parameters.doubles("k_act");
	k_off = parameters.doubles("k_off");
	k_exh = parameters.doubles("k_exh");
	k_rec_cart = parameters.doubles("k_rec_cart");
	r0_cart = parameters.doubles("r0_cart");
	eps_a = parameters.doubles("eps_a");
	lambda0_cart = parameters.doubles("lambda0_cart");
	lambda_AICD = parameters.doubles("lambda_AICD");
	p_AICD = parameters.doubles("p_AICD");
	k0_attack = parameters.doubles("k0_attack");
	dmg0 = parameters.doubles("dmg0");
	m_dmg = parameters.doubles("m_dmg");
	attack_duration_min = parameters.doubles("attack_duration_min");
	k_rep = parameters.doubles("k_rep");
	Dcrit = parameters.doubles("Dcrit");
	damage_Vmax = parameters.doubles("damage_Vmax");
	damage_Ksat = parameters.doubles("damage_Ksat");
	aux_uptake_rate = parameters.doubles("aux_uptake_rate");
	aux_secretion_Ksat = parameters.doubles("aux_secretion_Ksat");
	aux_params = get_aux_params( aux_cytokine_name );
	O2_boundary_value = parameters.doubles("O2_boundary_value");
	tumor_O2_uptake_rate = parameters.doubles("tumor_O2_uptake_rate");
	immune_O2_uptake_rate = parameters.doubles("immune_O2_uptake_rate");
	tumor_necrosis_rate = parameters.doubles("tumor_necrosis_rate");
	tumor_necrosis_O2_half_max = parameters.doubles("tumor_necrosis_O2_half_max");
	tumor_necrosis_hill_power = parameters.doubles("tumor_necrosis_hill_power");
	tumor_prolif_O2_half_max = parameters.doubles("tumor_prolif_O2_half_max");
	tumor_prolif_hill_power = parameters.doubles("tumor_prolif_hill_power");
	tumor_prolif_min_multiplier = parameters.doubles("tumor_prolif_min_multiplier");
	O2_quiescence_threshold = parameters.doubles("O2_quiescence_threshold");
	O2_necrosis_gate = parameters.doubles("O2_necrosis_gate");
	necrosis_damage_threshold = parameters.doubles("necrosis_damage_threshold");
	hypoxia_damage_repair_rate = parameters.doubles("hypoxia_damage_repair_rate");
	max_prolif_slowdown = parameters.doubles("max_prolif_slowdown");
	hypoxia_motility_boost = parameters.doubles("hypoxia_motility_boost");
	hypoxia_persistence_boost = parameters.doubles("hypoxia_persistence_boost");
	hypoxia_adhesion_drop = parameters.doubles("hypoxia_adhesion_drop");
	hypoxia_resistance_mult = parameters.doubles("hypoxia_resistance_mult");
	tumor_O2_hypoxia_threshold = parameters.doubles("tumor_O2_hypoxia_threshold");
	tumor_base_hypoxia_speed = parameters.doubles("tumor_base_hypoxia_speed");
	tumor_base_persistence_time = parameters.doubles("tumor_base_persistence_time");
	invasion_pressure_cutoff = parameters.doubles("invasion_pressure_cutoff");
	invasion_fraction_max = parameters.doubles("invasion_fraction_max");
	invasion_noise_strength = parameters.doubles("invasion_noise_strength");
	invasion_grad_eps = parameters.doubles("invasion_grad_eps");
	tumor_damage_per_contact = parameters.doubles("tumor_damage_per_contact");
	tumor_damage_threshold = parameters.doubles("tumor_damage_threshold");
	tumor_damage_necrosis_o2_threshold = parameters.doubles("tumor_damage_necrosis_o2_threshold");
	phagocytosis_rate_M0 = parameters.doubles("phagocytosis_rate_M0");
	phagocytosis_rate_M1 = parameters.doubles("phagocytosis_rate_M1");
	phagocytosis_rate_M2 = parameters.doubles("phagocytosis_rate_M2");
	tim3_gal9_strength = parameters.doubles("tim3_gal9_strength");
	p_M0_to_M1 = parameters.doubles("p_M0_to_M1");
	p_M0_to_M2 = parameters.doubles("p_M0_to_M2");
	O2_hypoxia_threshold = parameters.doubles("O2_hypoxia_threshold");
	O2_normoxia_threshold = parameters.doubles("O2_normoxia_threshold");
	k_antigen_present = parameters.doubles("k_antigen_present");
	antigen_contact_time_min = parameters.doubles("antigen_contact_time_min");
	naive_to_cd8_antigen_threshold = parameters.doubles("naive_to_cd8_antigen_threshold");
	naive_to_cd8_rate = parameters.doubles("naive_to_cd8_rate");
	naive_R_contact_APC = parameters.doubles("naive_R_contact_APC");
	naive_priming_min_time = parameters.doubles("naive_priming_min_time");
	naive_priming_decay_rate = parameters.doubles("naive_priming_decay_rate");
	naive_apc_weight_m0 = parameters.doubles("naive_apc_weight_m0");
	naive_apc_weight_m1 = parameters.doubles("naive_apc_weight_m1");
	naive_apc_weight_m2 = parameters.doubles("naive_apc_weight_m2");
	p_base_M1_to_M2 = parameters.doubles("p_base_M1_to_M2");
	M1_to_M2_O2_half = parameters.doubles("M1_to_M2_O2_half");
	M1_to_M2_hill_power = parameters.doubles("M1_to_M2_hill_power");
	m1_necrosis_O2_gate = parameters.doubles("m1_necrosis_O2_gate");
	m1_necrosis_O2_halfmax = parameters.doubles("m1_necrosis_O2_halfmax");
	m1_necrosis_hill_power = parameters.doubles("m1_necrosis_hill_power");
	m1_hypoxia_damage_rate = parameters.doubles("m1_hypoxia_damage_rate");
	m1_hypoxia_damage_repair_rate = parameters.doubles("m1_hypoxia_damage_repair_rate");
	m1_necrosis_damage_threshold = parameters.doubles("m1_necrosis_damage_threshold");
	m2_necrosis_O2_gate = parameters.doubles("m2_necrosis_O2_gate");
	m2_necrosis_O2_halfmax = parameters.doubles("m2_necrosis_O2_halfmax");
	m2_necrosis_hill_power = parameters.doubles("m2_necrosis_hill_power");
	m2_hypoxia_damage_rate = parameters.doubles("m2_hypoxia_damage_rate");
	m2_hypoxia_damage_repair_rate = parameters.doubles("m2_hypoxia_damage_repair_rate");
	m2_necrosis_damage_threshold = parameters.doubles("m2_necrosis_damage_threshold");
	m1_base_speed = parameters.doubles("m1_base_speed");
	m1_base_persistence = parameters.doubles("m1_base_persistence");
	m1_migration_bias = parameters.doubles("m1_migration_bias");
	m1_margin_preferred_radius = parameters.doubles("m1_margin_preferred_radius");
	m1_margin_band_width = parameters.doubles("m1_margin_band_width");
	m1_margin_bias_strength = parameters.doubles("m1_margin_bias_strength");
	m1_severe_hypoxia_O2 = parameters.doubles("m1_severe_hypoxia_O2");
	m1_seek_naive_radius = parameters.doubles("m1_seek_naive_radius");
	if( m1_margin_preferred_radius <= 0.0 )
	{
		m1_margin_preferred_radius = tumor_initial_radius;
	}
	m2_base_speed = parameters.doubles("m2_base_speed");
	m2_base_persistence = parameters.doubles("m2_base_persistence");
	m2_migration_bias = parameters.doubles("m2_migration_bias");
	m2_hypoxia_pref_min = parameters.doubles("m2_hypoxia_pref_min");
	m2_hypoxia_pref_max = parameters.doubles("m2_hypoxia_pref_max");
	m2_hypoxia_speed_boost = parameters.doubles("m2_hypoxia_speed_boost");
	m2_hypoxia_persistence_boost = parameters.doubles("m2_hypoxia_persistence_boost");

	N_tumor0 = parameters.ints("N_tumor0");
	N_CAR_T0 = parameters.ints("N_CAR_T0");
	max_spawn_attempts = parameters.ints("max_spawn_attempts");
	tumor_initial_radius = parameters.doubles("tumor_initial_radius");

	Bmax_Mphi = parameters.doubles("Bmax_Mphi");
	k_on_Mphi = parameters.doubles("k_on_Mphi");
	k_off_Mphi = parameters.doubles("k_off_Mphi");
	Kd_cis = parameters.doubles("Kd_cis");
	n_cis = parameters.doubles("n_cis");
	K_trans_CART = parameters.doubles("K_trans_CART");
	K_trans_CD8 = parameters.doubles("K_trans_CD8");
	w_trans_CART = parameters.doubles("w_trans_CART");
	w_cis_CART = parameters.doubles("w_cis_CART");
	w_trans_CD8 = parameters.doubles("w_trans_CD8");
	w_cis_CD8 = parameters.doubles("w_cis_CD8");
	k_int = parameters.doubles("k_int");
	k_rec = parameters.doubles("k_rec");
	alpha_death_CART = parameters.doubles("alpha_death_CART");
	alpha_exh_CART = parameters.doubles("alpha_exh_CART");
	alpha_prolif_CART = parameters.doubles("alpha_prolif_CART");
	alpha_death_CD8 = parameters.doubles("alpha_death_CD8");
	alpha_exh_CD8 = parameters.doubles("alpha_exh_CD8");
	alpha_prolif_CD8 = parameters.doubles("alpha_prolif_CD8");
	beta_exh = parameters.doubles("beta_exh");
	beta_kill = parameters.doubles("beta_kill");
	beta_surv = parameters.doubles("beta_surv");
	K_exh = parameters.doubles("K_exh");
	K_kill = parameters.doubles("K_kill");
	K_surv = parameters.doubles("K_surv");
	car_t_exhaustion_recovery_rate = parameters.doubles("carT_exhaustion_recovery_rate");
	cd8_exhaustion_recovery_rate = parameters.doubles("cd8_exhaustion_recovery_rate");
	il15_cis_consume_rate = parameters.doubles("il15_cis_consume_rate");
	il15_trans_consume_rate = parameters.doubles("il15_trans_consume_rate");
	car_t_base_apoptosis_rate = parameters.doubles("carT_base_apoptosis_rate");
	cd8_base_apoptosis_rate = parameters.doubles("cd8_base_apoptosis_rate");

	R_seek = parameters.doubles("R_seek");
	R_attach_CAR_T = parameters.doubles("R_attach_CAR_T");
	dwell_time_min_CAR_T = parameters.doubles("dwell_time_min_CAR_T");
	p_kill_CAR_T = parameters.doubles("p_kill_CAR_T");
	car_t_prolif_rate = parameters.doubles("carT_prolif_rate");
	car_t_exhaust_prolif_halfmax = parameters.doubles("carT_exhaust_prolif_halfmax");
	car_t_necrosis_O2_gate = parameters.doubles("carT_necrosis_O2_gate");
	car_t_necrosis_damage_rate = parameters.doubles("carT_necrosis_damage_rate");
	car_t_necrosis_damage_threshold = parameters.doubles("carT_necrosis_damage_threshold");
	car_t_exhaustion_per_kill = parameters.doubles("carT_exhaustion_per_kill");
	car_t_exhaustion_rate_when_attached = parameters.doubles("carT_exhaustion_rate_when_attached");
	car_t_exhaustion_threshold = parameters.doubles("carT_exhaustion_threshold");
	car_t_exhausted_kill_multiplier = parameters.doubles("carT_exhausted_kill_multiplier");
	car_t_exhaustion_increase_per_division = parameters.doubles("carT_exhaustion_increase_per_division");
	car_t_exhaustion_max = parameters.doubles("carT_exhaustion_max");
	car_t_terminal_exhaust_gate = parameters.doubles("carT_terminal_exhaust_gate");
	car_t_terminal_exhaust_time_min = parameters.doubles("carT_terminal_exhaust_time_min");
	car_t_terminal_death_rate = parameters.doubles("carT_terminal_death_rate");
	R_attach_CD8 = parameters.doubles("R_attach_CD8");
	dwell_time_min_CD8 = parameters.doubles("dwell_time_min_CD8");
	p_kill_CD8 = parameters.doubles("p_kill_CD8");
	cd8_prolif_rate = parameters.doubles("cd8_prolif_rate");
	cd8_exhaust_prolif_halfmax = parameters.doubles("cd8_exhaust_prolif_halfmax");
	cd8_exhaustion_increase_per_division = parameters.doubles("exhaustion_increase_per_division");
	cd8_exhaustion_max = parameters.doubles("exhaustion_max");
	cd8_necrosis_O2_gate = parameters.doubles("cd8_necrosis_O2_gate");
	cd8_necrosis_damage_rate = parameters.doubles("cd8_necrosis_damage_rate");
	cd8_necrosis_damage_threshold = parameters.doubles("cd8_necrosis_damage_threshold");
	cd8_sense_radius = parameters.doubles("cd8_sense_radius");
	cd8_bias_max = parameters.doubles("cd8_bias_max");
	cd8_terminal_exhaust_gate = parameters.doubles("cd8_terminal_exhaust_gate");
	cd8_terminal_exhaust_time_min = parameters.doubles("cd8_terminal_exhaust_time_min");
	cd8_terminal_death_rate = parameters.doubles("cd8_terminal_death_rate");
	exhaustion_per_kill = parameters.doubles("exhaustion_per_kill");
	exhaustion_rate_when_attached = parameters.doubles("exhaustion_rate_when_attached");
	exhaustion_threshold = parameters.doubles("exhaustion_threshold");
	exhausted_speed_multiplier = parameters.doubles("exhausted_speed_multiplier");
	exhausted_kill_multiplier = parameters.doubles("exhausted_kill_multiplier");
	exhaustion_E_max = parameters.doubles("E_max");
	O2_hypoxia_halfmax = parameters.doubles("O2_hypoxia_halfmax");
	hypoxia_hill_n = parameters.doubles("hypoxia_hill_n");
	hypoxia_exhaust_mult = parameters.doubles("hypoxia_exhaust_mult");
	M1_recovery_rate = parameters.doubles("M1_recovery_rate");
	M1_recovery_mult = parameters.doubles("M1_recovery_mult");
	M2_present_exhaust_rate = parameters.doubles("M2_present_exhaust_rate");
	M2_present_exhaust_per_event = parameters.doubles("M2_present_exhaust_per_event");

	spawn_radius_from_boundary = parameters.doubles("spawn_radius_from_boundary");
	metrics_interval_min = parameters.doubles("metrics_interval_min");
	snapshot_interval_min = parameters.doubles("snapshot_interval_min");

	number_of_naive_t_cells = parameters.ints("number_of_naive_t_cells");
	number_of_cd8_t_cells = parameters.ints("number_of_cd8_t_cells");
	number_of_exhausted_t_cells = parameters.ints("number_of_exhausted_t_cells");
	number_of_m0_macrophages = parameters.ints("number_of_m0_macrophages");
	number_of_m1_macrophages = parameters.ints("number_of_m1_macrophages");
	number_of_m2_macrophages = parameters.ints("number_of_m2_macrophages");
	initial_min_immune_distance_from_tumor = parameters.doubles("initial_min_immune_distance_from_tumor");
	thickness_of_immune_seeding_region = parameters.doubles("thickness_of_immune_seeding_region");

	tumor_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = tumor_O2_uptake_rate;
	car_t_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	naive_t_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	cd8_t_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	exhausted_t_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	macrophage_m0_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	macrophage_m1_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	macrophage_m2_cell_definition->phenotype.secretion.uptake_rates[oxygen_index] = immune_O2_uptake_rate;
	tumor_cell_definition->functions.update_phenotype = update_tumor_cell_phenotype;

	std::cout << "CD8 proliferation rate (cd8_prolif_rate): " << cd8_prolif_rate << " 1/min" << std::endl;

	car_t_cell_definition->functions.update_phenotype = update_car_t_cell_phenotype;
	car_t_cell_definition->functions.custom_cell_rule = immune_cell_rule;
	naive_t_cell_definition->functions.update_phenotype = update_naive_t_cell_phenotype;
	cd8_t_cell_definition->functions.update_phenotype = update_cd8_t_cell_phenotype;
	cd8_t_cell_definition->functions.custom_cell_rule = immune_cell_rule;
	exhausted_t_cell_definition->functions.update_phenotype = update_exhausted_t_cell_phenotype;

	macrophage_m0_cell_definition->functions.update_phenotype = update_macrophage_phenotype;
	macrophage_m0_cell_definition->functions.custom_cell_rule = macrophage_contact_rule;
	macrophage_m1_cell_definition->functions.update_phenotype = update_macrophage_phenotype;
	macrophage_m1_cell_definition->functions.custom_cell_rule = macrophage_contact_rule;
	macrophage_m2_cell_definition->functions.update_phenotype = update_macrophage_phenotype;
	macrophage_m2_cell_definition->functions.custom_cell_rule = macrophage_contact_rule;

	car_t_cell_definition->custom_data.add_variable( "exhaustion", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "is_exhausted", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "is_terminal_exhausted", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "time_high_exhaustion", "min", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "il15_signal", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "il15_receptor", "dimensionless", 1.0 );
	car_t_cell_definition->custom_data.add_variable( "activation", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "is_attacking", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "attack_damage_rate_now", "damage/min", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "attachment_rate", "1/min", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "kill_rate", "1/min", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "attachment_lifetime", "min", dwell_time_min_CAR_T );
	car_t_cell_definition->custom_data.add_variable( "max_attachment_distance", "micron", R_attach_CAR_T );
	car_t_cell_definition->custom_data.add_variable( "antigen_signal", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "time_attached", "min", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "attempted_kill_this_step", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "car_t_hypoxia_damage", "dimensionless", 0.0 );
	car_t_cell_definition->custom_data.add_variable( "exhaustion_increase_per_division", "dimensionless", car_t_exhaustion_increase_per_division );
	car_t_cell_definition->custom_data.add_variable( "exhaustion_max", "dimensionless", car_t_exhaustion_max );

	naive_t_cell_definition->custom_data.add_variable( "antigen_signal", "dimensionless", 0.0 );
	naive_t_cell_definition->custom_data.add_variable( "time_contact_APC", "min", 0.0 );

	cd8_t_cell_definition->custom_data.add_variable( "exhaustion", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "is_exhausted", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "attachment_rate", "1/min", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "kill_rate", "1/min", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "attachment_lifetime", "min", dwell_time_min_CD8 );
	cd8_t_cell_definition->custom_data.add_variable( "max_attachment_distance", "micron", R_attach_CD8 );
	cd8_t_cell_definition->custom_data.add_variable( "antigen_signal", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "il15_signal", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "il15_receptor", "dimensionless", 1.0 );
	cd8_t_cell_definition->custom_data.add_variable( "time_attached", "min", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "attempted_kill_this_step", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "exhaustion_increase_per_division", "dimensionless", cd8_exhaustion_increase_per_division );
	cd8_t_cell_definition->custom_data.add_variable( "exhaustion_max", "dimensionless", cd8_exhaustion_max );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_necrosis_O2_gate", "mmHg", cd8_necrosis_O2_gate );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_necrosis_damage_rate", "1/min", cd8_necrosis_damage_rate );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_necrosis_damage_threshold", "dimensionless", cd8_necrosis_damage_threshold );
	naive_t_cell_definition->custom_data.add_variable( "naive_hypoxia_damage", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_hypoxia_damage", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_terminal_exhaust_gate", "dimensionless", cd8_terminal_exhaust_gate );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_terminal_exhaust_time_min", "min", cd8_terminal_exhaust_time_min );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_terminal_death_rate", "1/min", cd8_terminal_death_rate );
	cd8_t_cell_definition->custom_data.add_variable( "is_terminal_exhausted", "dimensionless", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "time_high_exhaustion", "min", 0.0 );
	cd8_t_cell_definition->custom_data.add_variable( "cd8_kill_mult", "dimensionless", 1.0 );

	exhausted_t_cell_definition->custom_data.add_variable( "exhausted_origin_is_CAR_T", "dimensionless", 0.0 );

	macrophage_m0_cell_definition->custom_data.add_variable( "macrophage_bound_IL15", "dimensionless", 0.0 );
	macrophage_m1_cell_definition->custom_data.add_variable( "macrophage_bound_IL15", "dimensionless", 0.0 );
	macrophage_m2_cell_definition->custom_data.add_variable( "macrophage_bound_IL15", "dimensionless", 0.0 );
	macrophage_m0_cell_definition->custom_data.add_variable( "can_present_antigen", "dimensionless", 0.0 );
	macrophage_m1_cell_definition->custom_data.add_variable( "can_present_antigen", "dimensionless", 1.0 );
	macrophage_m2_cell_definition->custom_data.add_variable( "can_present_antigen", "dimensionless", 0.0 );
	macrophage_m2_cell_definition->custom_data.add_variable( "TIM3_Gal9_strength", "dimensionless", tim3_gal9_strength );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_necrosis_O2_gate", "mmHg", m1_necrosis_O2_gate );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_necrosis_O2_halfmax", "mmHg", m1_necrosis_O2_halfmax );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_necrosis_hill_power", "dimensionless", m1_necrosis_hill_power );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_hypoxia_damage_rate", "1/min", m1_hypoxia_damage_rate );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_hypoxia_damage_repair_rate", "1/min", m1_hypoxia_damage_repair_rate );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_necrosis_damage_threshold", "dimensionless", m1_necrosis_damage_threshold );
	macrophage_m1_cell_definition->custom_data.add_variable( "m1_hypoxia_damage", "dimensionless", 0.0 );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_necrosis_O2_gate", "mmHg", m2_necrosis_O2_gate );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_necrosis_O2_halfmax", "mmHg", m2_necrosis_O2_halfmax );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_necrosis_hill_power", "dimensionless", m2_necrosis_hill_power );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_hypoxia_damage_rate", "1/min", m2_hypoxia_damage_rate );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_hypoxia_damage_repair_rate", "1/min", m2_hypoxia_damage_repair_rate );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_necrosis_damage_threshold", "dimensionless", m2_necrosis_damage_threshold );
	macrophage_m2_cell_definition->custom_data.add_variable( "m2_hypoxia_damage", "dimensionless", 0.0 );
	tumor_cell_definition->custom_data.add_variable( "damage", "dimensionless", 0.0 );
	tumor_cell_definition->custom_data.add_variable( "last_damage_from_type", "dimensionless", -1.0 );
	tumor_cell_definition->custom_data.add_variable( "antigen", "dimensionless", 1.0 );
	tumor_cell_definition->custom_data.add_variable( "PDL1", "dimensionless", 0.0 );
	tumor_cell_definition->custom_data.add_variable( "hypoxia_damage", "dimensionless", 0.0 );
	tumor_cell_definition->custom_data.add_variable( "base_prolif_rate", "1/min", tumor_base_prolif_rate );
	tumor_cell_definition->custom_data.add_variable( "base_migration_speed", "micron/min",
		tumor_cell_definition->phenotype.motility.migration_speed );
	tumor_cell_definition->custom_data.add_variable( "base_persistence_time", "min",
		tumor_cell_definition->phenotype.motility.persistence_time );
	tumor_cell_definition->custom_data.add_variable( "base_adhesion_strength", "dimensionless",
		tumor_cell_definition->phenotype.mechanics.cell_cell_adhesion_strength );
	tumor_cell_definition->custom_data.add_variable( "tumor_resistance_mult", "dimensionless", 1.0 );

	// Ensure all cell types share a common custom_data schema (avoids thread-unsafe resizing later).
	ensure_custom_data_on_all_cell_definitions();

	// Cache hot custom_data indices (per definition).
	if( car_t_cell_definition )
	{
		idx_exhaustion_car_t = car_t_cell_definition->custom_data.find_variable_index( "exhaustion" );
		idx_il15_signal_car_t = car_t_cell_definition->custom_data.find_variable_index( "il15_signal" );
	}
	if( cd8_t_cell_definition )
	{
		idx_exhaustion_cd8 = cd8_t_cell_definition->custom_data.find_variable_index( "exhaustion" );
		idx_is_exhausted_cd8 = cd8_t_cell_definition->custom_data.find_variable_index( "is_exhausted" );
		idx_is_terminal_cd8 = cd8_t_cell_definition->custom_data.find_variable_index( "is_terminal_exhausted" );
	}
	if( exhausted_t_cell_definition )
	{
		idx_exhausted_origin_is_car_t =
			exhausted_t_cell_definition->custom_data.find_variable_index( "exhausted_origin_is_CAR_T" );
	}

	initialize_metrics_file();
	next_metrics_time = 0.0;
	next_snapshot_time = 0.0;
}

static std::vector<double> random_point_in_annulus( double r_inner, double r_outer )
{
	double theta = UniformRandom() * 2.0 * M_PI;
	double r = sqrt( (r_outer * r_outer - r_inner * r_inner) * UniformRandom() + r_inner * r_inner );
	return { r * cos( theta ), r * sin( theta ), 0.0 };
}

static void seed_tumor_as_central_disk( int target_count, double radius, double z0, int max_attempts )
{
	int created = 0;
	int attempts = 0;
	double min_dist = 0.0;
	while( created < target_count && attempts < max_attempts )
	{
		attempts++;
		double theta = UniformRandom() * 2.0 * M_PI;
		double r = radius * sqrt( UniformRandom() );
		double x = r * cos( theta );
		double y = r * sin( theta );

		bool overlap = false;
		for( size_t i = 0; i < (*all_cells).size(); i++ )
		{
			Cell* pOther = (*all_cells)[i];
			if( pOther->type != tumor_cell_type ) { continue; }
			double d = norm( pOther->position - std::vector<double>{ x, y, z0 } );
			if( d < min_dist )
			{
				overlap = true;
				break;
			}
		}
		if( overlap ) { continue; }

		Cell* pCell = create_cell( *tumor_cell_definition );
		pCell->custom_data["antigen"] = tumor_antigen_density;
		pCell->assign_position( x, y, z0 );
		created++;
	}
	std::cout << "Seeded tumor cells: " << created << " (requested " << target_count
	          << "), attempts=" << attempts << std::endl;
}

void setup_tissue( void )
{
	std::cout << "Seeding tumor..." << std::endl;
	double tumor_xmin = 1e9;
	double tumor_xmax = -1e9;
	double tumor_ymin = 1e9;
	double tumor_ymax = -1e9;
	seed_tumor_as_central_disk( N_tumor0, tumor_initial_radius, 0.0, max_spawn_attempts );
	for( size_t i = 0; i < (*all_cells).size(); i++ )
	{
		Cell* pCell = (*all_cells)[i];
		if( pCell->type != tumor_cell_type ) { continue; }
		double x = pCell->position[0];
		double y = pCell->position[1];
		tumor_xmin = std::min( tumor_xmin, x );
		tumor_xmax = std::max( tumor_xmax, x );
		tumor_ymin = std::min( tumor_ymin, y );
		tumor_ymax = std::max( tumor_ymax, y );
	}
	std::cout << "Tumor seeded: " << N_tumor0 << " cells; bbox x=[" << tumor_xmin << "," << tumor_xmax
	          << "], y=[" << tumor_ymin << "," << tumor_ymax << "]" << std::endl;

	double r_inner = tumor_initial_radius + initial_min_immune_distance_from_tumor;
	double r_outer = r_inner + thickness_of_immune_seeding_region;
	for( int i = 0; i < number_of_m0_macrophages; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *macrophage_m0_cell_definition );
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}
	for( int i = 0; i < number_of_m1_macrophages; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *macrophage_m1_cell_definition );
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}
	for( int i = 0; i < number_of_m2_macrophages; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *macrophage_m2_cell_definition );
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}
	for( int i = 0; i < number_of_naive_t_cells; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *naive_t_cell_definition );
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}
	for( int i = 0; i < number_of_cd8_t_cells; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *cd8_t_cell_definition );
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}
	for( int i = 0; i < number_of_exhausted_t_cells; i++ )
	{
		auto pos = random_point_in_annulus( r_inner, r_outer );
		Cell* pCell = create_cell( *exhausted_t_cell_definition );
		pCell->custom_data["exhausted_origin_is_CAR_T"] = 0.0;
		pCell->assign_position( pos[0], pos[1], 0.0 );
	}

	spawn_car_t_once();
}

void spawn_car_t_once( void )
{
	if( car_t_spawned_once || N_CAR_T0 <= 0 ) { return; }

	double xmin = microenvironment.mesh.bounding_box[0];
	double ymin = microenvironment.mesh.bounding_box[1];
	double xmax = microenvironment.mesh.bounding_box[3];
	double ymax = microenvironment.mesh.bounding_box[4];

	int spawned = 0;
	int failed = 0;
	for( int i = 0; i < N_CAR_T0; i++ )
	{
		bool placed = false;
		for( int attempt = 0; attempt < max_spawn_attempts; attempt++ )
		{
			double side = UniformRandom();
			double x = 0.0;
			double y = 0.0;
			if( side < 0.25 )
			{
				x = xmin + UniformRandom() * spawn_radius_from_boundary;
				y = UniformRandom() * (ymax - ymin) + ymin;
			}
			else if( side < 0.5 )
			{
				x = xmax - UniformRandom() * spawn_radius_from_boundary;
				y = UniformRandom() * (ymax - ymin) + ymin;
			}
			else if( side < 0.75 )
			{
				y = ymin + UniformRandom() * spawn_radius_from_boundary;
				x = UniformRandom() * (xmax - xmin) + xmin;
			}
			else
			{
				y = ymax - UniformRandom() * spawn_radius_from_boundary;
				x = UniformRandom() * (xmax - xmin) + xmin;
			}

			Cell* pCell = create_cell( *car_t_cell_definition );
			pCell->assign_position( x, y, 0.0 );
			spawned++;
			placed = true;
			break;
		}
		if( !placed ) { failed++; }
	}
	std::cout << "Spawned " << spawned << " CAR-T at boundary at t=0." << std::endl;
	if( failed > 0 )
	{
		std::cout << "Warning: CAR-T placement failed for " << failed << " cells." << std::endl;
	}
	car_t_spawned_once = true;
}

double hill_function( double x, double EC50, double n )
{
	double x_pow = fast_pow_n( x, n );
	double denom = fast_pow_n( EC50, n ) + x_pow;
	if( denom <= 0.0 ) { return 0.0; }
	return x_pow / denom;
}

void update_tumor_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	if( phenotype.death.dead ) { return; }
	double o2 = pCell->nearest_density_vector()[oxygen_index];
	double ratio_adapt = o2 / std::max( tumor_prolif_O2_half_max, 1e-12 );
	double hyp_adapt = 1.0 / ( 1.0 + fast_pow_n( ratio_adapt, tumor_prolif_hill_power ) );
	double ratio_nec = o2 / std::max( tumor_necrosis_O2_half_max, 1e-12 );
	double hyp_nec = 1.0 / ( 1.0 + fast_pow_n( ratio_nec, tumor_necrosis_hill_power ) );

	if( o2 < O2_necrosis_gate )
	{
		double damage = pCell->custom_data["hypoxia_damage"];
		damage += hyp_nec * dt;
		pCell->custom_data["hypoxia_damage"] = damage;
		if( damage >= necrosis_damage_threshold )
		{
			pCell->start_death( necrosis_index );
			return;
		}
	}
	else
	{
		double damage = pCell->custom_data["hypoxia_damage"];
		damage = std::max( 0.0, damage - hypoxia_damage_repair_rate * dt );
		pCell->custom_data["hypoxia_damage"] = damage;
	}

	double prolif_scale = 1.0 - max_prolif_slowdown * hyp_adapt;
	if( prolif_scale > 1.0 ) { prolif_scale = 1.0; }
	if( prolif_scale < 1.0 - max_prolif_slowdown ) { prolif_scale = 1.0 - max_prolif_slowdown; }
	double base_rate = pCell->custom_data["base_prolif_rate"];
	if( o2 < O2_quiescence_threshold )
	{
		phenotype.cycle.data.transition_rate( 0, 1 ) = 0.0;
	}
	else
	{
		phenotype.cycle.data.transition_rate( 0, 1 ) = base_rate * prolif_scale;
	}

	double base_adhesion = pCell->custom_data["base_adhesion_strength"];
	double adh_mult = 1.0 - hypoxia_adhesion_drop * hyp_adapt;
	if( adh_mult < 0.3 ) { adh_mult = 0.3; }
	if( adh_mult > 1.0 ) { adh_mult = 1.0; }

	if( o2 < tumor_O2_hypoxia_threshold )
	{
		if( pCell->state.simple_pressure < invasion_pressure_cutoff )
		{
			double p_invasion = invasion_fraction_max * hyp_adapt;
			if( p_invasion < 0.0 ) { p_invasion = 0.0; }
			if( p_invasion > invasion_fraction_max ) { p_invasion = invasion_fraction_max; }

			if( UniformRandom() < p_invasion )
			{
				phenotype.motility.is_motile = true;

				std::vector<double> radial = pCell->position - tumor_center;
				double rnorm = norm( radial );
				std::vector<double> dir( 3, 0.0 );
				if( rnorm > invasion_grad_eps )
				{
					dir = radial;
					normalize( dir );
				}
				else
				{
					dir = UniformOnUnitSphere();
				}

				std::vector<double> noise = UniformOnUnitSphere();
				noise *= invasion_noise_strength;
				dir += noise;
				normalize( dir );
				if( default_microenvironment_options.simulate_2D )
				{
					dir[2] = 0.0;
					normalize( dir );
				}

				double escape_strength = hyp_adapt;
				phenotype.motility.migration_speed =
					tumor_base_hypoxia_speed * ( 0.2 + 0.8 * escape_strength );
				phenotype.motility.persistence_time =
					tumor_base_persistence_time * ( 1.0 + hypoxia_persistence_boost * escape_strength );
				phenotype.motility.migration_bias_direction = dir;
				phenotype.motility.migration_bias = escape_strength;
			}
			else
			{
				phenotype.motility.is_motile = false;
				phenotype.motility.migration_speed = 0.0;
				phenotype.motility.migration_bias = 0.0;
			}
		}
		else
		{
			phenotype.motility.is_motile = false;
			phenotype.motility.migration_speed = 0.0;
			phenotype.motility.migration_bias = 0.0;
		}
	}
	else
	{
		phenotype.motility.is_motile = false;
		phenotype.motility.migration_speed = 0.0;
		phenotype.motility.migration_bias = 0.0;
	}
	phenotype.mechanics.cell_cell_adhesion_strength = base_adhesion * adh_mult;

	pCell->custom_data["tumor_resistance_mult"] = 1.0 + hypoxia_resistance_mult * hyp_adapt;

	// IFNg -> PDL1 induction (optional)
	if( enable_IFNg_PDL1_feedback && ifng_index >= 0 )
	{
		double c_ifng = pCell->nearest_density_vector()[ifng_index];
		double E_ifng = il15_hill( c_ifng, K_IFNg_PDL1, n_IFNg_PDL1 );
		double P = pCell->custom_data["PDL1"];
		double dP = ( k_PDL1_up * E_ifng * ( 1.0 - P ) - k_PDL1_down * P ) * dt;
		P = std::max( 0.0, std::min( 1.0, P + dP ) );
		pCell->custom_data["PDL1"] = P;
	}

	// Tumor damage from attached CAR-T (thread-safe: tumor updates its own damage)
	double damage = pCell->custom_data["damage"];
	double sum_dmg = 0.0;
	Cell* pCARSource = NULL;
	for( Cell* pAtt : pCell->state.attached_cells )
	{
		if( pAtt == NULL ) { continue; }
		if( pAtt->phenotype.death.dead ) { continue; }
		if( pAtt->type != car_t_cell_type ) { continue; }
		if( pAtt->custom_data["is_attacking"] < 0.5 ) { continue; }
		sum_dmg += pAtt->custom_data["attack_damage_rate_now"];
		if( pCARSource == NULL ) { pCARSource = pAtt; }
	}
	if( pCARSource != NULL )
	{
		pCell->custom_data["last_damage_from_type"] = (double) car_t_cell_type;
	}
	double sum_eff = sum_dmg;
	if( damage_Vmax > 0.0 && damage_Ksat > 0.0 )
	{
		sum_eff = damage_Vmax * sum_dmg / ( damage_Ksat + sum_dmg );
	}
	damage += ( sum_eff - k_rep * damage ) * dt;
	if( damage < 0.0 ) { damage = 0.0; }
	pCell->custom_data["damage"] = damage;

	if( damage >= Dcrit )
	{
		if( o2 < tumor_damage_necrosis_o2_threshold )
		{
			pCell->start_death( necrosis_index );
		}
		else
		{
			pCell->start_death( apoptosis_index );
		}
		int source_type = (int) pCell->custom_data["last_damage_from_type"];
		cumulative_tumor_kills += 1.0;
		if( source_type == car_t_cell_type )
		{
			cumulative_tumor_kills_CAR_T += 1.0;
			log_car_t_kill_event( pCARSource, pCell );
		}
		if( source_type == cd8_t_cell_type ) { cumulative_tumor_kills_CD8 += 1.0; }
	}
}

void update_car_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	if( phenotype.death.dead ) { return; }

	double local_o2 = 0.0;
	if( oxygen_index >= 0 )
	{
		local_o2 = pCell->nearest_density_vector()[oxygen_index];
	}
	if( local_o2 < car_t_necrosis_O2_gate )
	{
		double damage = pCell->custom_data["car_t_hypoxia_damage"];
		damage += car_t_necrosis_damage_rate * dt;
		pCell->custom_data["car_t_hypoxia_damage"] = damage;
		if( damage >= car_t_necrosis_damage_threshold )
		{
			cumulative_car_t_deaths += 1.0;
			pCell->start_death( necrosis_index );
			return;
		}
	}

	double il15_free = 0.0;
	if( il15_index >= 0 )
	{
		il15_free = pCell->nearest_density_vector()[il15_index];
	}
	double il15_trans = 0.0;
	double exhaustion = pCell->custom_data["exhaustion"];
	bool contact_with_tumor = false;
	bool contact_with_M2 = false;
	double attempted_kill = pCell->custom_data["attempted_kill_this_step"];

	std::vector<Cell*> neighbors = pCell->cells_in_my_container();
	NeighborContactInfo info = scan_neighbors( pCell, neighbors, true, true, true );
	contact_with_tumor = info.contact_tumor;
	contact_with_M2 = info.contact_m2;
	il15_trans = info.il15_trans;

	double R_cart = pCell->custom_data["il15_receptor"];
	double kill_rate = p_kill_CAR_T;
	double death_rate_eff = car_t_base_apoptosis_rate;
	double il15_signal = 0.0;
	double cis_signal = 0.0;
	double trans_signal = 0.0;
	update_Tcell_IL15_module(
		exhaustion,
		R_cart,
		il15_free,
		il15_trans,
		dt,
		local_o2,
		contact_with_tumor,
		contact_with_M2,
		false,
		( attempted_kill > 0.5 ),
		kill_rate,
		death_rate_eff,
		Kd_cis,
		n_cis,
		K_trans_CART,
		w_cis_CART,
		w_trans_CART,
		k_rec,
		k_int,
		car_t_exhaustion_rate_when_attached,
		car_t_exhaustion_per_kill,
		M2_present_exhaust_rate,
		0.0,
		p_kill_CAR_T,
		car_t_exhaustion_threshold,
		car_t_exhausted_kill_multiplier,
		car_t_base_apoptosis_rate,
		1.0,
		O2_hypoxia_halfmax,
		hypoxia_hill_n,
		hypoxia_exhaust_mult,
		car_t_exhaustion_recovery_rate,
		il15_signal,
		cis_signal,
		trans_signal
	);

	pCell->custom_data["il15_receptor"] = R_cart;
	pCell->custom_data["il15_signal"] = il15_signal;
	pCell->custom_data["exhaustion"] = exhaustion;
	pCell->custom_data["is_exhausted"] = ( exhaustion >= car_t_exhaustion_threshold ? 1.0 : 0.0 );

	// === Helper cytokine (aux) + IFNg module (screening) ===
	double a = pCell->custom_data["activation"];
	double e = pCell->custom_data["exhaustion"];
	double c_aux = ( aux_index >= 0 ) ? pCell->nearest_density_vector()[aux_index] : 0.0;
	double E_aux = il15_hill( c_aux, aux_params.K_cyto, aux_params.n_cyto );
	double G_gate = ( aux_params.use_gate ? a : 1.0 );
	double M_prolif = 1.0 + aux_params.alpha_prolif * E_aux;
	double M_surv = 1.0 + aux_params.alpha_surv * E_aux;
	double M_cyto = 1.0 + aux_params.alpha_cyto * E_aux * G_gate;
	double M_exh = 1.0;
	if( aux_params.alpha_exh < 0.0 )
	{
		M_exh = 1.0 / ( 1.0 + std::fabs( aux_params.alpha_exh ) * E_aux * G_gate );
	}
	else
	{
		M_exh = 1.0 + aux_params.alpha_exh * E_aux * G_gate;
	}

	double A_target = 1.0;
	double P_target = 0.0;
	double S = 0.0;
	if( pCell->state.number_of_attached_cells() > 0 )
	{
		Cell* pTarget = pCell->state.attached_cells[0];
		if( pTarget != NULL && !pTarget->phenotype.death.dead && pTarget->type == tumor_cell_type )
		{
			S = 1.0;
			A_target = pTarget->custom_data["antigen"];
			P_target = pTarget->custom_data["PDL1"];
		}
	}
	double H_A = il15_hill( A_target, K_A, n_A );

	// Activation / exhaustion dynamics
	double da = ( k_act * S * H_A * M_cyto - k_off * a ) * dt;
	double de = ( k_exh * S * H_A * M_exh - k_rec_cart * ( 1.0 - S ) * e ) * dt;
	a = std::max( 0.0, std::min( 1.0, a + da ) );
	e = std::max( 0.0, std::min( 1.0, e + de ) );
	pCell->custom_data["activation"] = a;
	pCell->custom_data["exhaustion"] = e;

	// Proliferation
	double r_prolif = r0_cart * M_prolif * ( eps_a + a ) * ( 1.0 - e );
	phenotype.cycle.data.transition_rate( 0, 1 ) = r_prolif;

	// Apoptosis (AICD)
	double lambda_death = ( M_surv > 0.0 ? lambda0_cart / M_surv : lambda0_cart )
		+ lambda_AICD * std::pow( a, p_AICD ) * ( 1.0 + aux_params.beta_AICD * E_aux );
	if( UniformRandom() < lambda_death * dt )
	{
		cumulative_car_t_deaths += 1.0;
		pCell->start_death( apoptosis_index );
		return;
	}

	// Attack rates (attach + damage)
	double attack_start_rate = k0_attack * H_A * ( 1.0 - e ) * M_cyto;
	double attack_damage_rate_now = dmg0 * H_A * std::pow( std::max( 0.0, 1.0 - e ), m_dmg ) * M_cyto;
	if( enable_IFNg_PDL1_feedback )
	{
		double P = std::max( 0.0, std::min( 1.0, P_target ) );
		double num = std::pow( K_PDL1_inhib, n_PDL1_inhib );
		double den = num + std::pow( P, n_PDL1_inhib );
		double inhib = ( den > 0.0 ? num / den : 1.0 );
		attack_start_rate *= inhib;
		attack_damage_rate_now *= inhib;
	}
	pCell->custom_data["attack_damage_rate_now"] = attack_damage_rate_now;
	pCell->custom_data["is_attacking"] = S;
	pCell->custom_data["attachment_rate"] = attack_start_rate;
	pCell->custom_data["attachment_lifetime"] = attack_duration_min;
	pCell->custom_data["kill_rate"] = 0.0;

	// IFNg secretion (always on when activated)
	if( ifng_index >= 0 )
	{
		double q_ifng = qIFNg_max * a * ( 1.0 - e );
		if( alpha_IFNg_aux > 0.0 )
		{
			q_ifng *= ( 1.0 + alpha_IFNg_aux * E_aux * G_gate );
		}
		pCell->phenotype.secretion.secretion_rates[ifng_index] = q_ifng;
		// BioFVM secretion uses rate * (target - C); set a positive target to enable secretion.
		pCell->phenotype.secretion.saturation_densities[ifng_index] = IFNg_secretion_target;
	}

	// Aux cytokine secretion
	if( aux_index >= 0 )
	{
		double q_aux = 0.0;
		// Mandatory aux uptake (e.g., IL-2 autocrine consumption)
		pCell->phenotype.secretion.uptake_rates[aux_index] = aux_uptake_rate;
		bool aux_is_il2 = ( aux_cytokine_name == "IL2" );
		bool aux_is_il21 = ( aux_cytokine_name == "IL21" );
		if( aux_mode == "bath" )
		{
			if( enable_endogenous_autocrine_for_IL2_IL21 && ( aux_is_il2 || aux_is_il21 ) )
			{
				double q_end = ( aux_is_il2 ? qmax_aux_endogenous_IL2 : qmax_aux_endogenous_IL21 );
				q_aux = q_end * a * ( 1.0 - e );
			}
		}
		else if( aux_mode == "armored" )
		{
			q_aux = qmax_aux_engineered * a * ( 1.0 - e );
		}
		// Secretion saturation vs local aux concentration
		if( aux_secretion_Ksat > 0.0 )
		{
			double sat = aux_secretion_Ksat / ( aux_secretion_Ksat + c_aux );
			q_aux *= sat;
		}
		pCell->phenotype.secretion.secretion_rates[aux_index] = q_aux;
		// BioFVM secretion uses rate * (target - C); set positive target for aux secretion.
		pCell->phenotype.secretion.saturation_densities[aux_index] = aux_secretion_Ksat;
	}

	// Signal-layer consumption: cis consumes local C, trans consumes bound IL15.
	if( il15_index >= 0 )
	{
		int v = microenvironment.nearest_voxel_index( pCell->position );
		double cval = microenvironment.density_vector(v)[il15_index];
		double dc = il15_cis_consume_rate * cis_signal * dt;
		if( dc > cval ) { dc = cval; }
		microenvironment.density_vector(v)[il15_index] = std::max( 0.0, cval - dc );
	}
	if( il15_trans > 0.0 && trans_signal > 0.0 )
	{
		std::vector<Cell*> neighbors = pCell->cells_in_my_container();
		for( Cell* pOther : neighbors )
		{
			if( pOther == pCell ) { continue; }
			if( pOther->type != macrophage_m0_cell_type && pOther->type != macrophage_m1_cell_type ) { continue; }
			double bound = pOther->custom_data["macrophage_bound_IL15"];
			if( bound <= 0.0 ) { continue; }
			double frac = bound / il15_trans;
			double dB = il15_trans_consume_rate * trans_signal * dt * frac;
			if( dB > bound ) { dB = bound; }
			pOther->custom_data["macrophage_bound_IL15"] = bound - dB;
		}
	}

	if( death_rate_eff > 0.0 && UniformRandom() < death_rate_eff * dt )
	{
		cumulative_car_t_deaths += 1.0;
		pCell->start_death( apoptosis_index );
		return;
	}
	// Clonal expansion with exhaustion-suppressed proliferation.
	double hE_prolif = 0.0;
	if( car_t_exhaust_prolif_halfmax > 0.0 )
	{
		double ex_pow = exhaustion * exhaustion;
		double half_pow = car_t_exhaust_prolif_halfmax * car_t_exhaust_prolif_halfmax;
		hE_prolif = ex_pow / ( ex_pow + half_pow );
	}
	double prolif_factor = 1.0 - hE_prolif;
	if( prolif_factor < 0.05 ) { prolif_factor = 0.05; }
	phenotype.cycle.data.transition_rate( 0, 1 ) = car_t_prolif_rate * prolif_factor;

	double E_gate = car_t_terminal_exhaust_gate;
	double T_gate = car_t_terminal_exhaust_time_min;
	bool terminal = ( pCell->custom_data["is_terminal_exhausted"] > 0.5 );
	if( !terminal )
	{
		if( exhaustion >= E_gate )
		{
			pCell->custom_data["time_high_exhaustion"] += dt;
		}
		else
		{
			pCell->custom_data["time_high_exhaustion"] = 0.0;
		}
		if( pCell->custom_data["time_high_exhaustion"] >= T_gate )
		{
			pCell->custom_data["is_terminal_exhausted"] = 1.0;
			cumulative_terminal_exhausted_car_t += 1.0;
			terminal = true;
		}
	}
	if( terminal )
	{
		phenotype.cycle.data.transition_rate( 0, 1 ) = 0.0;
		pCell->custom_data["attachment_rate"] = 0.0;
		pCell->custom_data["kill_rate"] = 0.0;
		double death_rate = car_t_terminal_death_rate;
		if( UniformRandom() < death_rate * dt )
		{
			cumulative_car_t_deaths += 1.0;
			pCell->start_death( apoptosis_index );
		}
		return;
	}

	if( exhaustion > car_t_exhaustion_threshold )
	{
		// Count exhausted-origin CAR-T cumulatively
		cumulative_exhausted_car_t += 1.0;
		pCell->convert_to_cell_definition( *exhausted_t_cell_definition );
		pCell->custom_data["exhausted_origin_is_CAR_T"] = 1.0;
		return;
	}

	pCell->custom_data["attachment_rate"] = 1.0;
	if( kill_rate > 1.0 ) { kill_rate = 1.0; }
	if( kill_rate < 0.0 ) { kill_rate = 0.0; }
	pCell->custom_data["kill_rate"] = kill_rate;
	pCell->custom_data["attachment_lifetime"] = dwell_time_min_CAR_T;
	pCell->custom_data["max_attachment_distance"] = R_attach_CAR_T;

	// direction toward nearest tumor (fallback to center if none found)
	std::vector<double> dir_to_tumor( 3, 0.0 );
	if( info.found_tumor )
	{
		double norm_dir = norm( info.dir_to_tumor );
		if( norm_dir > 1e-16 )
		{
			dir_to_tumor = ( 1.0 / norm_dir ) * info.dir_to_tumor;
		}
		else
		{
			dir_to_tumor = UniformOnUnitSphere();
		}
	}
	else
	{
		std::vector<double> dir_center = tumor_center - pCell->position;
		double norm_center = norm( dir_center );
		if( norm_center > 1e-16 )
		{
			dir_to_tumor = ( 1.0 / norm_center ) * dir_center;
		}
		else
		{
			dir_to_tumor = UniformOnUnitSphere();
		}
	}

	std::vector<double> bias_dir = dir_to_tumor;
	double norm_bias = norm( bias_dir );
	if( norm_bias > 1e-16 )
	{
		bias_dir *= ( 1.0 / norm_bias );
	}
	else
	{
		bias_dir = UniformOnUnitSphere();
	}

	if( default_microenvironment_options.simulate_2D )
	{
		bias_dir[2] = 0.0;
		double norm_xy = std::sqrt( bias_dir[0] * bias_dir[0] + bias_dir[1] * bias_dir[1] );
		if( norm_xy > 1e-16 )
		{
			bias_dir[0] /= norm_xy;
			bias_dir[1] /= norm_xy;
		}
	}

	phenotype.motility.migration_bias_direction = bias_dir;

	// Antigen presentation boosts attachment rate slightly and then decays.
	double antigen_signal = pCell->custom_data["antigen_signal"];
	if( antigen_signal > 0.0 )
	{
		pCell->custom_data["attachment_rate"] *= ( 1.0 + antigen_signal );
		antigen_signal = std::max( 0.0, antigen_signal - dt / std::max( antigen_contact_time_min, 1e-6 ) );
		pCell->custom_data["antigen_signal"] = antigen_signal;
	}

	if( pCell->custom_data["exhaustion"] > exhaustion_threshold )
	{
		phenotype.motility.migration_speed *= exhausted_speed_multiplier;
	}
}

void update_cd8_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	if( phenotype.death.dead ) { return; }
	double exhaustion = pCell->custom_data["exhaustion"];
	double time_attached = pCell->custom_data["time_attached"];
	double attempted_kill = pCell->custom_data["attempted_kill_this_step"];
	bool contact_with_tumor = false;
	bool contact_with_M1 = false;
	bool contact_with_M2 = false;
	std::vector<Cell*> neighbors = pCell->cells_in_my_container();
	NeighborContactInfo info = scan_neighbors( pCell, neighbors, true, true, true );
	contact_with_tumor = info.contact_tumor;
	contact_with_M1 = info.contact_m1;
	contact_with_M2 = info.contact_m2;

	double local_o2 = 0.0;
	if( oxygen_index >= 0 )
	{
		local_o2 = pCell->nearest_density_vector()[oxygen_index];
	}

	if( local_o2 < cd8_necrosis_O2_gate )
	{
		double damage = pCell->custom_data["cd8_hypoxia_damage"];
		damage += cd8_necrosis_damage_rate * dt;
		pCell->custom_data["cd8_hypoxia_damage"] = damage;
		if( damage >= cd8_necrosis_damage_threshold )
		{
			pCell->start_death( necrosis_index );
			return;
		}
	}
	double il15_free = 0.0;
	if( il15_index >= 0 )
	{
		il15_free = pCell->nearest_density_vector()[il15_index];
	}
	double R_cd8 = pCell->custom_data["il15_receptor"];
	double kill_rate = p_kill_CD8;
	double death_rate_eff = cd8_base_apoptosis_rate;
	double il15_signal_cd8 = 0.0;
	double cis_signal = 0.0;
	double trans_signal = 0.0;
	update_Tcell_IL15_module(
		exhaustion,
		R_cd8,
		il15_free,
		info.il15_trans,
		dt,
		local_o2,
		contact_with_tumor,
		contact_with_M2,
		contact_with_M1,
		( attempted_kill > 0.5 ),
		kill_rate,
		death_rate_eff,
		Kd_cis,
		n_cis,
		K_trans_CD8,
		w_cis_CD8,
		w_trans_CD8,
		k_rec,
		k_int,
		exhaustion_rate_when_attached,
		exhaustion_per_kill,
		M2_present_exhaust_rate,
		M1_recovery_rate,
		p_kill_CD8,
		exhaustion_threshold,
		exhausted_kill_multiplier,
		cd8_base_apoptosis_rate,
		1.0,
		O2_hypoxia_halfmax,
		hypoxia_hill_n,
		hypoxia_exhaust_mult,
		cd8_exhaustion_recovery_rate,
		il15_signal_cd8,
		cis_signal,
		trans_signal
	);

	pCell->custom_data["il15_receptor"] = R_cd8;
	pCell->custom_data["il15_signal"] = il15_signal_cd8;

	// Signal-layer consumption: cis consumes local C, trans consumes bound IL15.
	if( il15_index >= 0 )
	{
		int v = microenvironment.nearest_voxel_index( pCell->position );
		double cval = microenvironment.density_vector(v)[il15_index];
		double dc = il15_cis_consume_rate * cis_signal * dt;
		if( dc > cval ) { dc = cval; }
		microenvironment.density_vector(v)[il15_index] = std::max( 0.0, cval - dc );
	}
	if( info.il15_trans > 0.0 && trans_signal > 0.0 )
	{
		std::vector<Cell*> neighbors = pCell->cells_in_my_container();
		for( Cell* pOther : neighbors )
		{
			if( pOther == pCell ) { continue; }
			if( pOther->type != macrophage_m0_cell_type && pOther->type != macrophage_m1_cell_type ) { continue; }
			double bound = pOther->custom_data["macrophage_bound_IL15"];
			if( bound <= 0.0 ) { continue; }
			double frac = bound / info.il15_trans;
			double dB = il15_trans_consume_rate * trans_signal * dt * frac;
			if( dB > bound ) { dB = bound; }
			pOther->custom_data["macrophage_bound_IL15"] = bound - dB;
		}
	}
	if( death_rate_eff > 0.0 && UniformRandom() < death_rate_eff * dt )
	{
		pCell->start_death( apoptosis_index );
		return;
	}

	double cd8_emax = pCell->custom_data["exhaustion_max"];
	double max_e = ( cd8_emax > 0.0 ? cd8_emax : exhaustion_E_max );
	exhaustion = std::max( 0.0, std::min( exhaustion, max_e ) );
	pCell->custom_data["exhaustion"] = exhaustion;
	pCell->custom_data["is_exhausted"] = ( exhaustion >= exhaustion_threshold ? 1.0 : 0.0 );

	double E_gate = pCell->custom_data["cd8_terminal_exhaust_gate"];
	double T_gate = pCell->custom_data["cd8_terminal_exhaust_time_min"];
	bool terminal = ( pCell->custom_data["is_terminal_exhausted"] > 0.5 );
	if( !terminal )
	{
		if( exhaustion >= E_gate )
		{
			pCell->custom_data["time_high_exhaustion"] += dt;
		}
		else
		{
			pCell->custom_data["time_high_exhaustion"] = 0.0;
		}
		if( pCell->custom_data["time_high_exhaustion"] >= T_gate )
		{
			pCell->custom_data["is_terminal_exhausted"] = 1.0;
			terminal = true;
			cumulative_terminal_exhausted_cd8 += 1.0;
		}
	}

	if( terminal )
	{
		phenotype.cycle.data.transition_rate( 0, 1 ) = 0.0;
		pCell->custom_data["cd8_kill_mult"] = 0.0;
		phenotype.motility.is_motile = false;
		phenotype.motility.migration_speed = 0.0;
		phenotype.motility.migration_bias = 0.0;
		double death_rate = pCell->custom_data["cd8_terminal_death_rate"];
		if( UniformRandom() < death_rate * dt )
		{
			pCell->start_death( apoptosis_index );
			return;
		}
	}
	else
	{
		pCell->custom_data["cd8_kill_mult"] = 1.0;
	}

	// CD8 clonal expansion with exhaustion modulation.
	double hE_prolif = 0.0;
	if( cd8_exhaust_prolif_halfmax > 0.0 )
	{
		double ex_pow = exhaustion * exhaustion;
		double half_pow = cd8_exhaust_prolif_halfmax * cd8_exhaust_prolif_halfmax;
		hE_prolif = ex_pow / ( ex_pow + half_pow );
	}
	double prolif_factor = 1.0 - hE_prolif;
	if( prolif_factor < 0.05 ) { prolif_factor = 0.05; }
	phenotype.cycle.data.transition_rate( 0, 1 ) = cd8_prolif_rate * prolif_factor;

	kill_rate *= pCell->custom_data["cd8_kill_mult"];
	if( kill_rate > 1.0 ) { kill_rate = 1.0; }
	if( kill_rate < 0.0 ) { kill_rate = 0.0; }
	pCell->custom_data["attachment_rate"] = 1.0;
	pCell->custom_data["kill_rate"] = kill_rate;
	pCell->custom_data["attachment_lifetime"] = dwell_time_min_CD8;
	pCell->custom_data["max_attachment_distance"] = R_attach_CD8;

	// Antigen presentation boosts attachment rate slightly and then decays.
	double antigen_signal = pCell->custom_data["antigen_signal"];
	if( antigen_signal > 0.0 )
	{
		pCell->custom_data["attachment_rate"] *= ( 1.0 + antigen_signal );
		antigen_signal = std::max( 0.0, antigen_signal - dt / std::max( antigen_contact_time_min, 1e-6 ) );
		pCell->custom_data["antigen_signal"] = antigen_signal;
	}

	// CD8 tumor-seeking bias: move toward nearest tumor cell (not tumor center).
	if( pCell->custom_data["is_terminal_exhausted"] < 0.5 )
	{
		std::vector<double> rand_dir = UniformOnUnitSphere();
		std::vector<double> bias_dir = rand_dir;
		if( info.found_tumor )
		{
			double norm_dir = norm( info.dir_to_tumor );
			if( norm_dir > 1e-16 )
			{
				bias_dir = ( 1.0 / norm_dir ) * info.dir_to_tumor;
			}
			else
			{
				bias_dir = rand_dir;
			}
		}
		else
		{
			std::vector<double> dir_center = tumor_center - pCell->position;
			double norm_center = norm( dir_center );
			bias_dir = ( norm_center > 1e-16 ? ( 1.0 / norm_center ) * dir_center : rand_dir );
		}

		// Strong tumor-seeking: fixed bias strength toward tumor (no distance decay).
		double bias = std::max( 0.0, std::min( cd8_bias_max, 1.0 ) );

		if( default_microenvironment_options.simulate_2D )
		{
			bias_dir[2] = 0.0;
			double norm_xy = std::sqrt( bias_dir[0] * bias_dir[0] + bias_dir[1] * bias_dir[1] );
			if( norm_xy > 1e-16 )
			{
				bias_dir[0] /= norm_xy;
				bias_dir[1] /= norm_xy;
			}
		}

		// Use PhysiCell's built-in mixing of random walk + bias.
		phenotype.motility.migration_bias = bias;
		phenotype.motility.migration_bias_direction = bias_dir;
	}

}

void update_naive_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	( void ) phenotype;
	if( pCell->phenotype.death.dead ) { return; }

	double local_o2 = 0.0;
	if( oxygen_index >= 0 )
	{
		local_o2 = pCell->nearest_density_vector()[oxygen_index];
	}
	if( local_o2 < cd8_necrosis_O2_gate )
	{
		double damage = pCell->custom_data["naive_hypoxia_damage"];
		damage += cd8_necrosis_damage_rate * dt;
		pCell->custom_data["naive_hypoxia_damage"] = damage;
		if( damage >= cd8_necrosis_damage_threshold )
		{
			pCell->start_death( necrosis_index );
			return;
		}
	}

	// APC-driven priming: contact time + antigen signal integration.
	bool contacting_apc = false;
	double priming_input = 0.0;
	int apc_contacts = 0;
	std::vector<Cell*> neighbors = pCell->cells_in_my_container();
	for( size_t i = 0; i < neighbors.size(); i++ )
	{
		Cell* pOther = neighbors[i];
		if( pOther == pCell ) { continue; }
		if( pOther->phenotype.death.dead ) { continue; }
		if( pOther->type != macrophage_m0_cell_type &&
		    pOther->type != macrophage_m1_cell_type &&
		    pOther->type != macrophage_m2_cell_type )
		{ continue; }

		double contact_dist = pCell->phenotype.geometry.radius + pOther->phenotype.geometry.radius;
		if( naive_R_contact_APC > 0.0 )
		{
			contact_dist = std::max( contact_dist, naive_R_contact_APC );
		}
		double d2 = norm_squared( pOther->position - pCell->position );
		if( d2 > contact_dist * contact_dist ) { continue; }

		contacting_apc = true;
		apc_contacts++;
		double weight = naive_apc_weight_m0;
		if( pOther->type == macrophage_m1_cell_type ) { weight = naive_apc_weight_m1; }
		if( pOther->type == macrophage_m2_cell_type ) { weight = naive_apc_weight_m2; }
		priming_input = std::max( priming_input, weight );
	}

	if( contacting_apc )
	{
		pCell->custom_data["time_contact_APC"] += dt;
		antigen_presentation_events += (size_t)apc_contacts;
	}
	else
	{
		pCell->custom_data["time_contact_APC"] = 0.0;
	}

	double antigen_signal = pCell->custom_data["antigen_signal"];
	if( contacting_apc )
	{
		double k_on = naive_to_cd8_rate;
		double k_off = naive_priming_decay_rate;
		antigen_signal += ( k_on * priming_input * ( 1.0 - antigen_signal ) - k_off * antigen_signal ) * dt;
	}
	else
	{
		antigen_signal -= naive_priming_decay_rate * antigen_signal * dt;
	}
	antigen_signal = std::max( 0.0, std::min( 1.0, antigen_signal ) );
	pCell->custom_data["antigen_signal"] = antigen_signal;

	bool pass_signal = ( antigen_signal >= naive_to_cd8_antigen_threshold );
	bool pass_time = ( pCell->custom_data["time_contact_APC"] >= naive_priming_min_time );
	if( pass_signal && pass_time )
	{
		pCell->convert_to_cell_definition( *cd8_t_cell_definition );
		return;
	}
}

void update_exhausted_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	( void ) dt;
	if( phenotype.death.dead ) { return; }
	// Keep exhausted T motility consistent with CD8 baseline (no extra slowdown here).
	pCell->custom_data["kill_rate"] = 0.0;
	pCell->custom_data["attachment_rate"] = 0.0;
	pCell->custom_data["max_attachment_distance"] = 0.0;
}

static bool macrophage_near_necrotic_tumor( Cell* pCell )
{
	std::vector<Cell*> neighbors = pCell->cells_in_my_container();
	for( size_t i = 0; i < neighbors.size(); i++ )
	{
		Cell* pOther = neighbors[i];
		if( pOther == pCell ) { continue; }
		if( pOther->type != tumor_cell_type ) { continue; }
		if( !pOther->phenotype.death.dead ) { continue; }
		if( pOther->phenotype.death.current_death_model_index != necrosis_index ) { continue; }
		double contact_dist = pOther->phenotype.geometry.radius + pCell->phenotype.geometry.radius;
		double d2 = norm_squared( pOther->position - pCell->position );
		if( d2 <= contact_dist * contact_dist ) { return true; }
	}
	return false;
}

static double hypoxia_hill_inverse( double o2, double halfmax, double n )
{
	if( o2 <= 0.0 ) { return 1.0; }
	double ratio = o2 / std::max( halfmax, 1e-12 );
	return 1.0 / ( 1.0 + fast_pow_n( ratio, n ) );
}

static double il15_cis_signal( double c_local )
{
	if( c_local <= 0.0 ) { return 0.0; }
	double num = std::pow( c_local, n_cis );
	double den = num + std::pow( Kd_cis, n_cis );
	if( den <= 0.0 ) { return 0.0; }
	return num / den;
}

static double il15_trans_signal( double bsum, double K_trans )
{
	if( bsum <= 0.0 ) { return 0.0; }
	double den = bsum + K_trans;
	if( den <= 0.0 ) { return 0.0; }
	return bsum / den;
}

static double il15_or_combine( double a, double b )
{
	return 1.0 - ( 1.0 - a ) * ( 1.0 - b );
}

static inline double il15_hill( double x, double K, double n )
{
	double num = std::pow( x, n );
	double den = num + std::pow( K, n ) + 1e-16;
	return num / den;
}

static void update_Tcell_IL15_module(
	double& E,
	double& R,
	double C,
	double Bsum,
	double dt,
	double O2,
	bool contact_with_tumor,
	bool contact_with_M2,
	bool contact_with_M1,
	bool attempted_kill,
	double& kill_rate,
	double& death_rate_eff,
	double Kd_cis_local,
	double n_cis_local,
	double K_trans_local,
	double w_cis_local,
	double w_trans_local,
	double k_rec_local,
	double k_int_local,
	double exhaustion_rate_when_attached,
	double exhaustion_per_kill,
	double M2_present_exhaust_rate_local,
	double M1_recovery_rate_local,
	double p_kill,
	double exhaustion_threshold_local,
	double exhausted_kill_multiplier_local,
	double death_rate_base,
	double tumor_resistance_mult,
	double O2_half,
	double hypoxia_hill,
	double hypoxia_exhaust_mult,
	double recovery_rate,
	double& il15_signal_out,
	double& cis_signal_out,
	double& trans_signal_out
)
{
	double cis = il15_hill( C, Kd_cis_local, n_cis_local );
	double trans = ( Bsum > 0.0 ? Bsum / ( Bsum + K_trans_local ) : 0.0 );
	double Sraw = 1.0 - ( 1.0 - w_cis_local * cis ) * ( 1.0 - w_trans_local * trans );
	R += dt * ( k_rec_local * ( 1.0 - R ) - k_int_local * Sraw * R );
	if( R < 0.0 ) { R = 0.0; }
	if( R > 1.0 ) { R = 1.0; }
	double IL15_signal = Sraw * R;
	il15_signal_out = IL15_signal;
	cis_signal_out = cis;
	trans_signal_out = trans;

	double h_exh = il15_hill( IL15_signal, K_exh, 2.0 );
	double h_kill = il15_hill( IL15_signal, K_kill, 2.0 );
	double h_surv = il15_hill( IL15_signal, K_surv, 2.0 );

	double il15_exh_mult = 1.0 / ( 1.0 + beta_exh * h_exh );
	// Disable IL-15 direct boost to killing.
	double g_kill_IL15 = 1.0;
	double g_surv_IL15 = 1.0 - beta_surv * h_surv;

	double ratio = O2 / std::max( O2_half, 1e-12 );
	double hyp = 1.0 / ( 1.0 + std::pow( ratio, hypoxia_hill ) );
	double hyp_mult = 1.0 + hypoxia_exhaust_mult * hyp;

	if( contact_with_tumor )
	{
		E += exhaustion_rate_when_attached * hyp_mult * il15_exh_mult * dt;
		if( attempted_kill )
		{
			E += exhaustion_per_kill * il15_exh_mult;
		}
	}
	if( contact_with_M2 )
	{
		E += M2_present_exhaust_rate_local * il15_exh_mult * dt;
	}
	if( contact_with_M1 )
	{
		E -= M1_recovery_rate_local * dt;
	}
	E -= recovery_rate * h_exh * dt;
	if( E < 0.0 ) { E = 0.0; }

	double hE = E / ( E + exhaustion_threshold_local );
	double exhaust_factor = ( 1.0 - hE ) + exhausted_kill_multiplier_local * hE;
	kill_rate = p_kill * exhaust_factor * g_kill_IL15;
	if( tumor_resistance_mult > 1.0 ) { kill_rate /= tumor_resistance_mult; }

	death_rate_eff = death_rate_base * g_surv_IL15;
	if( death_rate_eff < 0.0 ) { death_rate_eff = 0.0; }
}

static void update_M1_hypoxia_necrosis( Cell* pCell, double dt )
{
	double o2 = pCell->nearest_density_vector()[oxygen_index];
	double gate = pCell->custom_data["m1_necrosis_O2_gate"];
	double halfmax = pCell->custom_data["m1_necrosis_O2_halfmax"];
	double n = pCell->custom_data["m1_necrosis_hill_power"];
	double dmg_rate = pCell->custom_data["m1_hypoxia_damage_rate"];
	double repair_rate = pCell->custom_data["m1_hypoxia_damage_repair_rate"];
	double dmg_thresh = pCell->custom_data["m1_necrosis_damage_threshold"];
	double hyp_nec = hypoxia_hill_inverse( o2, halfmax, n );

	double damage = pCell->custom_data["m1_hypoxia_damage"];
	if( o2 < gate )
	{
		damage += dmg_rate * hyp_nec * dt;
		pCell->custom_data["m1_hypoxia_damage"] = damage;
		if( damage >= dmg_thresh )
		{
			pCell->start_death( necrosis_index );
		}
	}
	else
	{
		damage = std::max( 0.0, damage - repair_rate * dt );
		pCell->custom_data["m1_hypoxia_damage"] = damage;
	}
}

static void update_M2_hypoxia_necrosis( Cell* pCell, double dt )
{
	double o2 = pCell->nearest_density_vector()[oxygen_index];
	double gate = pCell->custom_data["m2_necrosis_O2_gate"];
	double halfmax = pCell->custom_data["m2_necrosis_O2_halfmax"];
	double n = pCell->custom_data["m2_necrosis_hill_power"];
	double dmg_rate = pCell->custom_data["m2_hypoxia_damage_rate"];
	double repair_rate = pCell->custom_data["m2_hypoxia_damage_repair_rate"];
	double dmg_thresh = pCell->custom_data["m2_necrosis_damage_threshold"];
	double hyp_nec = hypoxia_hill_inverse( o2, halfmax, n );

	double damage = pCell->custom_data["m2_hypoxia_damage"];
	if( o2 < gate )
	{
		damage += dmg_rate * hyp_nec * dt;
		pCell->custom_data["m2_hypoxia_damage"] = damage;
		if( damage >= dmg_thresh )
		{
			pCell->start_death( necrosis_index );
		}
	}
	else
	{
		damage = std::max( 0.0, damage - repair_rate * dt );
		pCell->custom_data["m2_hypoxia_damage"] = damage;
	}
}

void update_macrophage_phenotype( Cell* pCell, Phenotype& phenotype, double dt )
{
	( void ) phenotype;
	if( phenotype.death.dead ) { return; }
	double il15_free = pCell->nearest_density_vector()[il15_index];
	double bound = pCell->custom_data["macrophage_bound_IL15"];
	if( pCell->type == macrophage_m0_cell_type || pCell->type == macrophage_m1_cell_type )
	{
		double bmax = std::max( 0.0, Bmax_Mphi );
		double dB = k_on_Mphi * il15_free * ( bmax - bound ) - k_off_Mphi * bound;
		bound += dB * dt;
		if( bound < 0.0 ) { bound = 0.0; }
		if( bound > bmax ) { bound = bmax; }
	}
	else
	{
		bound = 0.0;
	}
	pCell->custom_data["macrophage_bound_IL15"] = bound;

	// Rule-based polarization: M0 -> M1 (normoxia), M0 -> M2 (hypoxia or necrotic contact).
	if( pCell->type == macrophage_m0_cell_type )
	{
		double o2 = pCell->nearest_density_vector()[oxygen_index];
		bool near_necrotic = macrophage_near_necrotic_tumor( pCell );
		if( o2 < O2_hypoxia_threshold || near_necrotic )
		{
			if( UniformRandom() < p_M0_to_M2 * dt )
			{
				pCell->convert_to_cell_definition( *macrophage_m2_cell_definition );
				pCell->custom_data["can_present_antigen"] = 0.0;
				return;
			}
		}
		else if( o2 > O2_normoxia_threshold )
		{
			if( UniformRandom() < p_M0_to_M1 * dt )
			{
				pCell->convert_to_cell_definition( *macrophage_m1_cell_definition );
				pCell->custom_data["can_present_antigen"] = 1.0;
				return;
			}
		}
	}
	// Rule-based polarization: M1 -> M2 under low oxygen (Hill on O2_half / O2).
	else if( pCell->type == macrophage_m1_cell_type )
	{
		double o2 = pCell->nearest_density_vector()[oxygen_index];
		if( o2 > 0.0 && p_base_M1_to_M2 > 0.0 )
		{
			double ratio = M1_to_M2_O2_half / o2;
			double ratio_pow = fast_pow_n( ratio, M1_to_M2_hill_power );
			double hill = ratio_pow / ( 1.0 + ratio_pow );
			double p_switch = p_base_M1_to_M2 * hill;
			if( UniformRandom() < p_switch * dt )
			{
				pCell->convert_to_cell_definition( *macrophage_m2_cell_definition );
				pCell->custom_data["can_present_antigen"] = 0.0;
				return;
			}
		}
	}

	if( pCell->type == macrophage_m1_cell_type )
	{
		update_M1_hypoxia_necrosis( pCell, dt );
	}
	else if( pCell->type == macrophage_m2_cell_type )
	{
		update_M2_hypoxia_necrosis( pCell, dt );
	}

	// Distinct macrophage motility (M1: slow patrol, M2: faster/infiltrative).
	if( pCell->type == macrophage_m1_cell_type )
	{
		double o2 = pCell->nearest_density_vector()[oxygen_index];
		if( o2 < m1_severe_hypoxia_O2 )
		{
			pCell->start_death( necrosis_index );
			return;
		}

		// Intermittent local patrol (25% of steps move).
		if( UniformRandom() > 0.25 )
		{
			phenotype.motility.is_motile = false;
			phenotype.motility.migration_speed = 0.0;
			phenotype.motility.migration_bias = 0.0;
			return;
		}

		double speed = m1_base_speed;
		double persistence = m1_base_persistence;
		double bias = m1_migration_bias;
		if( bias > 0.2 ) { bias = 0.2; }
		if( persistence > 6.0 ) { persistence = 6.0; }

		phenotype.motility.is_motile = true;
		phenotype.motility.migration_speed = speed;
		phenotype.motility.persistence_time = persistence;
		phenotype.motility.migration_bias = bias;

		std::vector<double> dir_random = UniformOnUnitSphere();
		if( default_microenvironment_options.simulate_2D ) { dir_random[2] = 0.0; }

		// Seek nearest naive T cell if within search radius; otherwise random patrol.
		std::vector<double> dir_seek = dir_random;
		double best_d2 = 1e99;
		bool found_naive = false;
		double R_seek = std::max( m1_seek_naive_radius, 0.0 );
		double R2 = R_seek * R_seek;
		std::vector<Cell*> local = pCell->cells_in_my_container();
		for( size_t i = 0; i < local.size(); i++ )
		{
			Cell* pOther = local[i];
			if( pOther == pCell ) { continue; }
			if( pOther->type != naive_t_cell_type ) { continue; }
			if( pOther->phenotype.death.dead ) { continue; }
			std::vector<double> dv = pOther->position - pCell->position;
			double d2 = norm_squared( dv );
			if( d2 > R2 ) { continue; }
			if( d2 < best_d2 )
			{
				best_d2 = d2;
				dir_seek = dv;
				found_naive = true;
			}
		}
		if( found_naive )
		{
			double norm_seek = norm( dir_seek );
			if( norm_seek > 1e-16 )
			{
				dir_seek *= ( 1.0 / norm_seek );
			}
			else
			{
				dir_seek = dir_random;
			}
		}
		else
		{
			dir_seek = dir_random;
		}
		if( default_microenvironment_options.simulate_2D )
		{
			dir_seek[2] = 0.0;
			double norm_xy = std::sqrt( dir_seek[0] * dir_seek[0] + dir_seek[1] * dir_seek[1] );
			if( norm_xy > 1e-16 )
			{
				dir_seek[0] /= norm_xy;
				dir_seek[1] /= norm_xy;
			}
		}
		phenotype.motility.migration_bias_direction = dir_seek;
	}
	else if( pCell->type == macrophage_m2_cell_type )
	{
		phenotype.motility.is_motile = true;
		double speed = m2_base_speed;
		double persistence = m2_base_persistence;
		double o2 = pCell->nearest_density_vector()[oxygen_index];
		if( o2 >= m2_hypoxia_pref_min && o2 <= m2_hypoxia_pref_max )
		{
			speed *= m2_hypoxia_speed_boost;
			persistence *= m2_hypoxia_persistence_boost;
		}
		phenotype.motility.migration_speed = speed;
		phenotype.motility.persistence_time = persistence;
		phenotype.motility.migration_bias = m2_migration_bias;
		std::vector<double> dir = UniformOnUnitSphere();
		if( default_microenvironment_options.simulate_2D )
		{
			dir[2] = 0.0;
			double norm_xy = std::sqrt( dir[0] * dir[0] + dir[1] * dir[1] );
			if( norm_xy > 1e-16 )
			{
				dir[0] /= norm_xy;
				dir[1] /= norm_xy;
			}
			else
			{
				dir[0] = 1.0;
				dir[1] = 0.0;
			}
		}
		phenotype.motility.migration_bias_direction = dir;
	}
}

Cell* immune_cell_check_neighbors_for_attachment( Cell* pAttacker , double dt )
{
	std::vector<Cell*> nearby = pAttacker->cells_in_my_container();
	for( size_t i = 0; i < nearby.size(); i++ )
	{
		if( nearby[i] == pAttacker ) { continue; }
		if( immune_cell_attempt_attachment( pAttacker, nearby[i], dt ) )
		{ return nearby[i]; }
	}
	return NULL;
}

bool immune_cell_attempt_attachment( Cell* pAttacker, Cell* pTarget , double dt )
{
	if( pTarget->type != tumor_cell_type ) { return false; }
	if( pTarget->phenotype.death.dead ) { return false; }
	double max_attachment_distance = pAttacker->custom_data["max_attachment_distance"];
	double d2 = norm_squared( pTarget->position - pAttacker->position );
	if( d2 > max_attachment_distance * max_attachment_distance ) { return false; }
	double attach_rate = pAttacker->custom_data["attachment_rate"];
	if( pAttacker->type == car_t_cell_type )
	{
		attach_rate *= tumor_antigen_activation( pTarget );
	}
	if( UniformRandom() < attach_rate * dt )
	{
		attach_cells( pAttacker, pTarget );
		return true;
	}
	return false;
}

bool immune_cell_attempt_apoptosis( Cell* pAttacker, Cell* pTarget, double dt )
{
	if( pTarget->phenotype.death.dead ) { return false; }
	double kill_rate = pAttacker->custom_data["kill_rate"];
	if( pAttacker->type == car_t_cell_type )
	{
		kill_rate *= tumor_antigen_activation( pTarget );
	}
	int resist_index = pTarget->custom_data.find_variable_index( "tumor_resistance_mult" );
	if( resist_index >= 0 )
	{
		double resist = pTarget->custom_data.variables[resist_index].value;
		if( resist > 1.0 ) { kill_rate /= resist; }
	}
	if( UniformRandom() < kill_rate * dt ) { return true; }
	return false;
}

bool immune_cell_trigger_apoptosis( Cell* pAttacker, Cell* pTarget )
{
	if( pTarget->phenotype.death.dead ) { return false; }
	if( pTarget->type != tumor_cell_type ) { return false; }
	pTarget->start_death( apoptosis_index );
	cumulative_tumor_kills += 1.0;
	if( pAttacker->type == car_t_cell_type )
	{
		cumulative_tumor_kills_CAR_T += 1.0;
		log_car_t_kill_event( pAttacker, pTarget );
	}
	else if( pAttacker->type == cd8_t_cell_type )
	{
		cumulative_tumor_kills_CD8 += 1.0;
	}
	return true;
}

void apply_damage_to_tumor( Cell* pTarget, Cell* pAttacker, double dt )
{
	if( pTarget->phenotype.death.dead ) { return; }
	if( pAttacker == NULL ) { return; }
	double damage = pTarget->custom_data["damage"];
	double damage_rate = tumor_damage_per_contact;
	if( pAttacker->type == cd8_t_cell_type )
	{
		damage_rate *= pAttacker->custom_data["cd8_kill_mult"];
	}
	damage += damage_rate * dt;
	pTarget->custom_data["damage"] = damage;
	pTarget->custom_data["last_damage_from_type"] = (double) pAttacker->type;
}

void immune_cell_rule( Cell* pCell, Phenotype& phenotype, double dt )
{
	if( phenotype.death.dead ) { return; }
	if( pCell->state.number_of_attached_cells() > 0 )
	{
		pCell->custom_data["attempted_kill_this_step"] = 0.0;
		double time_attached = pCell->custom_data["time_attached"];
		time_attached += dt;
		pCell->custom_data["time_attached"] = time_attached;
		bool detach_me = false;
		double attach_lifetime = pCell->custom_data["attachment_lifetime"];
		if( time_attached >= attach_lifetime )
		{
			pCell->custom_data["attempted_kill_this_step"] = 1.0;
			if( immune_cell_attempt_apoptosis( pCell, pCell->state.attached_cells[0], dt ) )
			{
				immune_cell_trigger_apoptosis( pCell, pCell->state.attached_cells[0] );
				detach_me = true;
			}
		}
		if( pCell->type != car_t_cell_type )
		{
			apply_damage_to_tumor( pCell->state.attached_cells[0], pCell, dt );
		}
		if( UniformRandom() < dt / ( attach_lifetime + 1e-15 ) )
		{ detach_me = true; }
		if( detach_me )
		{
			detach_cells( pCell, pCell->state.attached_cells[0] );
			phenotype.motility.is_motile = true;
			pCell->custom_data["time_attached"] = 0.0;
			pCell->custom_data["attempted_kill_this_step"] = 0.0;
		}
		return;
	}

	pCell->custom_data["time_attached"] = 0.0;
	pCell->custom_data["attempted_kill_this_step"] = 0.0;
	if( immune_cell_check_neighbors_for_attachment( pCell , dt ) )
	{
		phenotype.motility.is_motile = false;
		return;
	}
	if( pCell->type == cd8_t_cell_type && pCell->custom_data["is_terminal_exhausted"] > 0.5 )
	{
		phenotype.motility.is_motile = false;
		phenotype.motility.migration_speed = 0.0;
		phenotype.motility.migration_bias = 0.0;
		return;
	}
	phenotype.motility.is_motile = true;
}

void macrophage_contact_rule( Cell* pCell, Phenotype& phenotype, double dt )
{
	( void ) phenotype;
	if( pCell->phenotype.death.dead ) { return; }
	double phago_rate = phagocytosis_rate_M0;
	if( pCell->type == macrophage_m1_cell_type ) { phago_rate = phagocytosis_rate_M1; }
	if( pCell->type == macrophage_m2_cell_type ) { phago_rate = phagocytosis_rate_M2; }

	// Antigen presentation handled in naive T cell phenotype update.

	std::vector<Cell*> neighbors = pCell->cells_in_my_container();
	for( size_t i = 0; i < neighbors.size(); i++ )
	{
		Cell* pTarget = neighbors[i];
		if( pTarget == pCell ) { continue; }
		if( !pTarget->phenotype.death.dead ) { continue; }
		if( pTarget->phenotype.death.current_death_model_index != apoptosis_index &&
		    pTarget->phenotype.death.current_death_model_index != necrosis_index )
		{
			continue;
		}
		double contact_dist = pTarget->phenotype.geometry.radius + pCell->phenotype.geometry.radius;
		double d2 = norm_squared( pTarget->position - pCell->position );
		if( d2 > contact_dist * contact_dist ) { continue; }
		if( UniformRandom() < phago_rate * dt )
		{
			pTarget->lyse_cell();
		}
	}
}

void adhesion_contact_function( Cell* pActingOn, Phenotype& pao, Cell* pAttachedTo, Phenotype& pat , double dt )
{
	( void ) pat;
	( void ) dt;
	std::vector<double> displacement = pAttachedTo->position - pActingOn->position;
	double max_elastic_displacement = pao.geometry.radius * pao.mechanics.relative_detachment_distance;
	double max_displacement_squared = max_elastic_displacement * max_elastic_displacement;
	if( norm_squared( displacement ) > max_displacement_squared )
	{
		detach_cells( pActingOn , pAttachedTo );
		return;
	}
	axpy( &(pActingOn->velocity) , pao.mechanics.attachment_elastic_constant , displacement );
}

void update_custom_outputs( double dt )
{
	if( PhysiCell_globals.current_time >= next_metrics_time - 0.5 * dt )
	{
		size_t tumor_count = 0;
		size_t car_t_count = 0;
		size_t cd8_t_count = 0;
		size_t naive_t_count = 0;
		size_t exhausted_t_count = 0;
		size_t exhausted_car_t_count = 0;
		size_t exhausted_cd8_flag_count = 0;
		size_t exhausted_car_t_flag_count = 0;
		size_t terminal_exhausted_cd8_count = 0;
		size_t terminal_exhausted_car_t_flag_count = 0;
		size_t macrophage_total = 0;
		size_t m0 = 0;
		size_t m1 = 0;
		size_t m2 = 0;
		size_t attached_t_count = 0;
		size_t attached_car_t_count = 0;
		size_t attached_cd8_count = 0;
		size_t attached_m2_car_t_count = 0;
		size_t attached_m2_cd8_count = 0;
		size_t attached_naive_m1_count = 0;
		size_t attached_cd8_m1_count = 0;
		size_t attached_naive_m0_count = 0;
		size_t attached_cd8_m0_count = 0;
		double sum_exhaustion_car_t = 0.0;
		double sum_activation_car_t = 0.0;
		double sum_exhaustion_cd8 = 0.0;
		double sum_il15_signal_car_t = 0.0;
		double sum_il15_signal_cd8 = 0.0;
		std::vector<double> center_pos = { 0.0, 0.0, 0.0 };
		int center_voxel = microenvironment.nearest_voxel_index( center_pos );
		size_t tumor_center_voxel_count = 0;
		double tumor_o2_sum = 0.0;
		double tumor_o2_uptake_flux_sum = 0.0;
		double tumor_center_voxel_volume_sum = 0.0;
		double min_tumor_o2 = 1e9;
		double max_tumor_o2 = -1e9;
		double sample_tumor_o2 = -1.0;
		double sample_tumor_uptake = 0.0;
		bool have_tumor_sample = false;

		for( size_t i = 0; i < (*all_cells).size(); i++ )
		{
			Cell* pCell = (*all_cells)[i];
			if( pCell->type == tumor_cell_type )
			{
				if( pCell->is_out_of_domain ) { continue; }
				if( pCell->phenotype.death.dead ) { continue; }
				tumor_count++;
				if( oxygen_index < 0 ) { continue; }
				std::vector<double>& local_density = pCell->nearest_density_vector();
				if( oxygen_index >= (int) local_density.size() ) { continue; }
				double o2 = local_density[oxygen_index];
				tumor_o2_sum += o2;
				tumor_o2_uptake_flux_sum += tumor_O2_uptake_rate * o2;
				min_tumor_o2 = std::min( min_tumor_o2, o2 );
				max_tumor_o2 = std::max( max_tumor_o2, o2 );
				if( !have_tumor_sample )
				{
					sample_tumor_o2 = o2;
					sample_tumor_uptake = tumor_O2_uptake_rate * o2;
					have_tumor_sample = true;
				}
				if( microenvironment.nearest_voxel_index( pCell->position ) == center_voxel )
				{
					tumor_center_voxel_count++;
					tumor_center_voxel_volume_sum += pCell->phenotype.volume.total;
				}
			}
			else if( pCell->type == car_t_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				car_t_count++;
				if( idx_exhaustion_car_t >= 0 ) { sum_exhaustion_car_t += pCell->custom_data.variables[idx_exhaustion_car_t].value; }
				else { sum_exhaustion_car_t += pCell->custom_data["exhaustion"]; }
				sum_activation_car_t += pCell->custom_data["activation"];
				if( idx_il15_signal_car_t >= 0 ) { sum_il15_signal_car_t += pCell->custom_data.variables[idx_il15_signal_car_t].value; }
				else { sum_il15_signal_car_t += pCell->custom_data["il15_signal"]; }
				double is_exh_car_t = pCell->custom_data["is_exhausted"];
				if( is_exh_car_t > 0.5 )
				{
					exhausted_car_t_flag_count++;
				}
				double is_term_car_t = pCell->custom_data["is_terminal_exhausted"];
				if( is_term_car_t > 0.5 )
				{
					terminal_exhausted_car_t_flag_count++;
				}
				bool contact_tumor = false;
				bool contact_m2 = false;
				std::vector<Cell*> neighbors = pCell->cells_in_my_container();
				NeighborContactInfo info = scan_neighbors( pCell, neighbors, false, false, true );
				contact_tumor = info.contact_tumor;
				contact_m2 = info.contact_m2;
				if( contact_tumor )
				{
					attached_t_count++;
					attached_car_t_count++;
				}
				if( contact_m2 ) { attached_m2_car_t_count++; }
			}
			else if( pCell->type == naive_t_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				naive_t_count++;
				bool contact_m1 = false;
				bool contact_m0 = false;
				std::vector<Cell*> neighbors = pCell->cells_in_my_container();
				NeighborContactInfo info = scan_neighbors( pCell, neighbors, false, false, true );
				contact_m1 = info.contact_m1;
				contact_m0 = info.contact_m0;
				if( contact_m1 ) { attached_naive_m1_count++; }
				if( contact_m0 ) { attached_naive_m0_count++; }
			}
			else if( pCell->type == cd8_t_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				cd8_t_count++;
				if( idx_exhaustion_cd8 >= 0 ) { sum_exhaustion_cd8 += pCell->custom_data.variables[idx_exhaustion_cd8].value; }
				else { sum_exhaustion_cd8 += pCell->custom_data["exhaustion"]; }
				sum_il15_signal_cd8 += pCell->custom_data["il15_signal"];
				double is_exh = ( idx_is_exhausted_cd8 >= 0 )
					? pCell->custom_data.variables[idx_is_exhausted_cd8].value
					: pCell->custom_data["is_exhausted"];
				if( is_exh > 0.5 )
				{
					exhausted_cd8_flag_count++;
				}
				double is_term = ( idx_is_terminal_cd8 >= 0 )
					? pCell->custom_data.variables[idx_is_terminal_cd8].value
					: pCell->custom_data["is_terminal_exhausted"];
				if( is_term > 0.5 )
				{
					terminal_exhausted_cd8_count++;
				}
				bool contact_tumor = false;
				bool contact_m2 = false;
				bool contact_m1 = false;
				bool contact_m0 = false;
				std::vector<Cell*> neighbors = pCell->cells_in_my_container();
				NeighborContactInfo info = scan_neighbors( pCell, neighbors, false, false, true );
				contact_tumor = info.contact_tumor;
				contact_m2 = info.contact_m2;
				contact_m1 = info.contact_m1;
				contact_m0 = info.contact_m0;
				if( contact_tumor )
				{
					attached_t_count++;
					attached_cd8_count++;
				}
				if( contact_m2 ) { attached_m2_cd8_count++; }
				if( contact_m1 ) { attached_cd8_m1_count++; }
				if( contact_m0 ) { attached_cd8_m0_count++; }
			}
			else if( pCell->type == exhausted_t_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				exhausted_t_count++;
				double origin_is_car_t = ( idx_exhausted_origin_is_car_t >= 0 )
					? pCell->custom_data.variables[idx_exhausted_origin_is_car_t].value
					: pCell->custom_data["exhausted_origin_is_CAR_T"];
				if( origin_is_car_t > 0.5 )
				{
					exhausted_car_t_count++;
					// count exhausted-origin CAR-T toward exhausted flag count
					exhausted_car_t_flag_count++;
				}
			}
			else if( pCell->type == macrophage_m0_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				macrophage_total++; m0++;
			}
			else if( pCell->type == macrophage_m1_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				macrophage_total++; m1++;
			}
			else if( pCell->type == macrophage_m2_cell_type )
			{
				if( pCell->phenotype.death.dead ) { continue; }
				macrophage_total++; m2++;
			}
		}
		double il15_sum = 0.0;
		double il15_max = 0.0;
		double aux_sum = 0.0;
		double aux_max = 0.0;
		double ifng_sum = 0.0;
		double ifng_max = 0.0;
		double o2_min = 1e9;
		double o2_max = -1e9;
		double o2_sum = 0.0;
		for( int v = 0; v < microenvironment.number_of_voxels(); v++ )
		{
			double il15_val = microenvironment.density_vector(v)[il15_index];
			il15_sum += il15_val;
			if( il15_val > il15_max ) { il15_max = il15_val; }
			if( aux_index >= 0 )
			{
				double aux_val = microenvironment.density_vector(v)[aux_index];
				aux_sum += aux_val;
				if( aux_val > aux_max ) { aux_max = aux_val; }
			}
			if( ifng_index >= 0 )
			{
				double ifng_val = microenvironment.density_vector(v)[ifng_index];
				ifng_sum += ifng_val;
				if( ifng_val > ifng_max ) { ifng_max = ifng_val; }
			}
			double o2_val = microenvironment.density_vector(v)[oxygen_index];
			o2_sum += o2_val;
			o2_min = std::min( o2_min, o2_val );
			o2_max = std::max( o2_max, o2_val );
		}
		double il15_mean = il15_sum / (double) microenvironment.number_of_voxels();
		if( il15_index >= 0 )
		{
			// IL15 log output suppressed
		}
		double o2_mean = o2_sum / (double) microenvironment.number_of_voxels();
		IL15_AUC_total += il15_mean * metrics_interval_min;
		tumor_AUC += (double) tumor_count * metrics_interval_min;

		double mean_exhaustion_car_t = 0.0;
		double mean_activation_car_t = 0.0;
		double mean_exhaustion_cd8 = 0.0;
		double mean_il15_signal_car_t = 0.0;
		double mean_il15_signal_cd8 = 0.0;
		double exhaustion_fraction_car_t = 0.0;
		double exhaustion_fraction_cd8 = 0.0;
		size_t car_t_total_for_frac = car_t_count + exhausted_car_t_count;
		if( car_t_count > 0 )
		{
			mean_exhaustion_car_t = sum_exhaustion_car_t / (double) car_t_count;
			mean_activation_car_t = sum_activation_car_t / (double) car_t_count;
			mean_il15_signal_car_t = sum_il15_signal_car_t / (double) car_t_count;
		}
		if( car_t_total_for_frac > 0 )
		{
			exhaustion_fraction_car_t = (double) exhausted_car_t_flag_count / (double) car_t_total_for_frac;
		}
		if( cd8_t_count > 0 )
		{
			mean_exhaustion_cd8 = sum_exhaustion_cd8 / (double) cd8_t_count;
			mean_il15_signal_cd8 = sum_il15_signal_cd8 / (double) cd8_t_count;
			exhaustion_fraction_cd8 = (double) exhausted_cd8_flag_count / (double) cd8_t_count;
		}

		double time_day = PhysiCell_globals.current_time / 1440.0;
		// IL15 SWEEP ADDITION
		metrics_file << PhysiCell_globals.current_time << "," << time_day << ","
		             << tumor_count << "," << car_t_count << "," << cumulative_exhausted_car_t << ","
		             << terminal_exhausted_car_t_flag_count << "," << cumulative_terminal_exhausted_car_t << ","
		             << cumulative_tumor_kills << ","
		             << cumulative_tumor_kills_CAR_T << "," << mean_exhaustion_car_t << ","
		             << mean_il15_signal_car_t << "," << exhaustion_fraction_car_t << ","
		             << cumulative_car_t_deaths
		             << std::endl;
		metrics_file.flush();

		// Screening metrics.csv
		if( !screening_file.is_open() )
		{
			std::string fname = PhysiCell_settings.folder + "/metrics.csv";
			screening_file.open( fname.c_str(), std::ios::out );
			screening_file.setf( std::ios::scientific );
			screening_file << std::setprecision( 10 );
			screening_file << "time_min,live_tumor_count,live_cart_count,mean_cart_activation,mean_cart_exhaustion,mean_aux_cytokine,mean_IFNg,mean_tumor_PDL1,tumor_remaining_fraction\n";
		}
		double mean_aux = ( aux_index >= 0 ? aux_sum / (double) microenvironment.number_of_voxels() : 0.0 );
		double mean_ifng = ( ifng_index >= 0 ? ifng_sum / (double) microenvironment.number_of_voxels() : 0.0 );
		double tumor_pdl1_sum = 0.0;
		if( tumor_count > 0 )
		{
			for( size_t i = 0; i < (*all_cells).size(); i++ )
			{
				Cell* pCell = (*all_cells)[i];
				if( pCell == NULL ) { continue; }
				if( pCell->type != tumor_cell_type ) { continue; }
				if( pCell->phenotype.death.dead ) { continue; }
				tumor_pdl1_sum += pCell->custom_data["PDL1"];
			}
		}
		double mean_pdl1 = ( tumor_count > 0 ? tumor_pdl1_sum / (double) tumor_count : 0.0 );
		double tumor_remaining_fraction = ( N_tumor0 > 0 ? (double) tumor_count / (double) N_tumor0 : 0.0 );
		screening_file << PhysiCell_globals.current_time << ","
		              << tumor_count << ","
		              << car_t_count << ","
		              << mean_activation_car_t << ","
		              << mean_exhaustion_car_t << ","
		              << mean_aux << ","
		              << mean_ifng << ","
		              << mean_pdl1 << ","
		              << tumor_remaining_fraction
		              << std::endl;
		screening_file.flush();

		// (log output suppressed)
		if( tumor_count > 0 && have_tumor_sample )
		{
			double tumor_center_voxel_volume_frac = 0.0;
			double voxel_volume = microenvironment.mesh.voxels[center_voxel].volume;
			if( voxel_volume > 0.0 )
			{
				tumor_center_voxel_volume_frac = tumor_center_voxel_volume_sum / voxel_volume;
			}
		}

		next_metrics_time += metrics_interval_min;
	}

	if( PhysiCell_globals.current_time >= next_snapshot_time - 0.5 * dt )
	{
		char filename[1024];
		sprintf( filename , "%s/snapshot%08u.svg" , PhysiCell_settings.folder.c_str() , frame_id );
		SVG_plot( filename , microenvironment , 0.0 , PhysiCell_globals.current_time , tumor_immune_cell_coloring );
		if( !fast_test_mode )
		{
			strip_svg_time_and_agents( filename );
		}
		frame_id++;
		next_snapshot_time += snapshot_interval_min;
	}

	// IL15 SWEEP ADDITION: guaranteed day 3/5/7 snapshots
	const double day3_min = 3.0 * 24.0 * 60.0;
	const double day5_min = 5.0 * 24.0 * 60.0;
	const double day7_min = 7.0 * 24.0 * 60.0;
	if( !snap_day3_done && PhysiCell_globals.current_time >= day3_min - 0.5 * dt )
	{
		char f3[1024];
		sprintf( f3 , "%s/snap_day3.svg" , PhysiCell_settings.folder.c_str() );
		SVG_plot( f3 , microenvironment , 0.0 , PhysiCell_globals.current_time , tumor_immune_cell_coloring );
		snap_day3_done = true;
	}
	if( !snap_day5_done && PhysiCell_globals.current_time >= day5_min - 0.5 * dt )
	{
		char f5[1024];
		sprintf( f5 , "%s/snap_day5.svg" , PhysiCell_settings.folder.c_str() );
		SVG_plot( f5 , microenvironment , 0.0 , PhysiCell_globals.current_time , tumor_immune_cell_coloring );
		snap_day5_done = true;
	}
	if( !snap_day7_done && PhysiCell_globals.current_time >= day7_min - 0.5 * dt )
	{
		char f7[1024];
		sprintf( f7 , "%s/snap_day7.svg" , PhysiCell_settings.folder.c_str() );
		SVG_plot( f7 , microenvironment , 0.0 , PhysiCell_globals.current_time , tumor_immune_cell_coloring );
		snap_day7_done = true;
	}
}

void force_metrics_write( double dt )
{
	next_metrics_time = PhysiCell_globals.current_time;
	update_custom_outputs( dt );
}

bool tumor_all_dead( void )
{
	if( all_cells == NULL ) { return true; }
	for( size_t i = 0; i < (*all_cells).size(); i++ )
	{
		Cell* pCell = (*all_cells)[i];
		if( pCell == NULL ) { continue; }
		if( pCell->type != tumor_cell_type ) { continue; }
		if( pCell->phenotype.death.dead ) { continue; }
		return false;
	}
	return true;
}

bool car_t_all_dead( void )
{
	if( all_cells == NULL ) { return true; }
	for( size_t i = 0; i < (*all_cells).size(); i++ )
	{
		Cell* pCell = (*all_cells)[i];
		if( pCell == NULL ) { continue; }
		if( pCell->type != car_t_cell_type ) { continue; }
		if( pCell->phenotype.death.dead ) { continue; }
		return false;
	}
	return true;
}
