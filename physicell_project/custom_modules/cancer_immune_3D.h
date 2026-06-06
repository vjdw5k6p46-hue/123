#ifndef CANCER_IMMUNE_3D_H
#define CANCER_IMMUNE_3D_H

#include "../core/PhysiCell.h"
#include "../modules/PhysiCell_standard_modules.h"

using namespace BioFVM;
using namespace PhysiCell;

extern Cell_Definition* tumor_cell_definition;
extern Cell_Definition* car_t_cell_definition;
extern Cell_Definition* naive_t_cell_definition;
extern Cell_Definition* cd8_t_cell_definition;
extern Cell_Definition* exhausted_t_cell_definition;
extern Cell_Definition* macrophage_m0_cell_definition;
extern Cell_Definition* macrophage_m1_cell_definition;
extern Cell_Definition* macrophage_m2_cell_definition;

extern int tumor_cell_type;
extern int car_t_cell_type;
extern int naive_t_cell_type;
extern int cd8_t_cell_type;
extern int exhausted_t_cell_type;
extern int macrophage_m0_cell_type;
extern int macrophage_m1_cell_type;
extern int macrophage_m2_cell_type;

extern double IL15_C_baseline;
extern double IL15_C_dose;
extern double IL15_on_duration_min;
extern double IL15_start_time_min;
extern double IL15_period_min;
extern double IL15_free_half_life_min;
extern double IL15_decay_rate;


extern double metrics_interval_min;
extern double snapshot_interval_min;
extern double z_slice_thickness;
extern int png_width;
extern int png_height;

extern double IL15_AUC_total;
extern double tumor_AUC;
extern double cumulative_tumor_kills;
extern double w_auc;

extern bool fast_test_mode;
extern double debug_center_o2_pre;

void create_cell_types( void );
void setup_microenvironment( void );
void setup_tissue( void );
void spawn_car_t_once( void );
void update_vessel_dirichlet_conditions( void );
void update_custom_outputs( double dt );
bool tumor_all_dead( void );
void force_metrics_write( double dt );
bool car_t_all_dead( void );

void update_tumor_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void update_car_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void update_naive_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void update_cd8_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void update_exhausted_t_cell_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void update_macrophage_phenotype( Cell* pCell, Phenotype& phenotype, double dt );
void macrophage_contact_rule( Cell* pCell, Phenotype& phenotype, double dt );

Cell* immune_cell_check_neighbors_for_attachment( Cell* pAttacker , double dt );
bool immune_cell_attempt_attachment( Cell* pAttacker, Cell* pTarget , double dt );
bool immune_cell_attempt_apoptosis( Cell* pAttacker, Cell* pTarget, double dt );
bool immune_cell_trigger_apoptosis( Cell* pAttacker, Cell* pTarget );
void immune_cell_rule( Cell* pCell, Phenotype& phenotype, double dt );
void adhesion_contact_function( Cell* pActingOn, Phenotype& pao, Cell* pAttachedTo, Phenotype& pat , double dt );

double hill_function( double x, double EC50, double n );
double compute_il15_trans_signal( Cell* pCell );
bool check_tumor_contact( Cell* pCell );
void apply_damage_to_tumor( Cell* pTarget, int attacker_type, double dt );

#endif
